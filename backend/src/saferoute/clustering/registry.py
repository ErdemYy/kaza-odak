"""Deney kaydı: deterministik deney kimliği, durum ve sonuç kalıcılığı.

Deney kimliği; algoritma, parametreler, öznitelik seti, kapsam (alt küme tanımı), veri sürümü
ve kod sürümünden türetilir (zaman damgası içermez) → aynı deney her koşuda aynı kimliği alır.
Başarısız veya kaynak sınırı nedeniyle çalıştırılmayan deneyler de durum ve hata bilgisiyle kaydedilir.
"""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from saferoute.clustering.settings import CLUSTERING_CODE_VERSION, stable_hash

STATUSES = ("success", "failed", "skipped_resource_limit")


def experiment_id(algorithm: str, params: dict[str, Any], feature_set: str, scope: dict[str, Any] | None,
                  dataset_version: str) -> str:
    key = {"algorithm": algorithm, "params": params, "feature_set": feature_set, "scope": scope or {},
           "dataset_version": dataset_version, "code_version": CLUSTERING_CODE_VERSION}
    return f"{algorithm}-{stable_hash(key, 10)}"


def software_versions() -> dict[str, str]:
    import numpy
    import pandas
    import scipy
    import sklearn

    out = {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": numpy.__version__,
           "pandas": pandas.__version__, "scipy": scipy.__version__, "platform": platform.platform()}
    try:
        from importlib.metadata import version

        out["hdbscan"] = version("hdbscan")
    except Exception:
        pass
    return out


@dataclass
class ExperimentRecord:
    experiment_id: str
    stage: str
    algorithm: str
    params: dict[str, Any]
    feature_set: str
    scope: dict[str, Any]
    dataset_version: str
    processing_version: str
    status: str
    error: str | None = None
    n_events: int | None = None
    n_unique_locations: int | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    runtime_s: float | None = None
    peak_memory_mb: float | None = None
    memory_before_fit_mb: float | None = None
    warnings: list[str] = field(default_factory=list)
    seed: int | None = None
    labels_path: str | None = None
    software: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"Geçersiz durum: {self.status}")
        if self.status != "success" and not self.error:
            raise ValueError("Başarısız/atlanan deney hata açıklaması içermeli")


class Registry:
    """JSON tabanlı deney kaydı; aynı kimlikli kayıt güncellenir, sıralama kimliğe göre deterministiktir."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for r in json.loads(self.path.read_text(encoding="utf-8")):
                self.records[r["experiment_id"]] = r

    def add(self, record: ExperimentRecord) -> None:
        self.records[record.experiment_id] = asdict(record)
        self.save()

    def get(self, exp_id: str) -> dict[str, Any] | None:
        return self.records.get(exp_id)

    def by_stage(self, stage: str) -> list[dict[str, Any]]:
        return [r for r in self.ordered() if r["stage"] == stage]

    def ordered(self) -> list[dict[str, Any]]:
        return [self.records[k] for k in sorted(self.records)]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.ordered(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self.path)
