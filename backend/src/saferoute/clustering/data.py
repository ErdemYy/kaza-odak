"""Faz 2 çıktılarının yüklenmesi, hizalama doğrulaması ve deney alt kümeleri.

Olay (event) = kümelemeye uygun bir kaza kaydı. Her olay bir benzersiz konuma
(``location_index``) bağlıdır; ağırlıklı temsil, bir alt kümedeki olayların konumlara
göre sayılmasıyla (ağırlık = olay sayısı) üretilir. Satır sırası Faz 2 öznitelik
matrisleriyle (``collision_id`` sırası) aynıdır ve korunur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from saferoute import config
from saferoute.data.loader import latest_snapshot

EVENT_COLUMNS = [
    "collision_id", "location_id", "eligible_for_spatial_clustering", "latitude", "longitude",
    "lat_rad", "lon_rad", "x_m", "y_m", "crash_year", "midnight_suspect_flag",
    "geocode_fallback_suspect_flag", "borough_conflict_flag", "coordinate_quality_status",
]


class AlignmentError(RuntimeError):
    """Matrisler ve işlenmiş katman arasında kimlik/sıra/ağırlık uyuşmazlığı."""


def processed_dir(snapshot_name: str | None = None) -> Path:
    name = snapshot_name or latest_snapshot().name
    return config.PROCESSED_DIR / config.DATASET_ID / name


@dataclass
class EventData:
    collision_id: np.ndarray
    location_index: np.ndarray
    lat_rad: np.ndarray
    lon_rad: np.ndarray
    x_m: np.ndarray
    y_m: np.ndarray
    year: np.ndarray
    flags: dict[str, np.ndarray]
    loc_lat_rad: np.ndarray
    loc_lon_rad: np.ndarray
    loc_x_m: np.ndarray
    loc_y_m: np.ndarray
    loc_weight: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def n_events(self) -> int:
        return len(self.collision_id)

    @property
    def n_locations(self) -> int:
        return len(self.loc_weight)


def load_events(pdir: Path | None = None) -> EventData:
    """Uygun olayları ve benzersiz konum tablosunu yükler (sıra korunur)."""
    pdir = Path(pdir or processed_dir())
    p = pd.read_parquet(pdir / "crashes_processed.parquet", columns=EVENT_COLUMNS)
    e = p[p["eligible_for_spatial_clustering"]]
    locs = pd.read_parquet(pdir / "locations.parquet")
    side = json.loads((pdir / "crashes_processed.parquet.json").read_text(encoding="utf-8"))
    return EventData(
        collision_id=e["collision_id"].to_numpy(dtype=np.int64),
        location_index=e["location_id"].to_numpy(dtype=np.int64),
        lat_rad=e["lat_rad"].to_numpy(), lon_rad=e["lon_rad"].to_numpy(),
        x_m=e["x_m"].to_numpy(), y_m=e["y_m"].to_numpy(),
        year=e["crash_year"].to_numpy(dtype=np.int16),
        flags={
            "midnight": e["midnight_suspect_flag"].to_numpy(bool),
            "geocode_fallback": e["geocode_fallback_suspect_flag"].to_numpy(bool),
            "borough_conflict": e["borough_conflict_flag"].to_numpy(bool),
            "nearshore": (e["coordinate_quality_status"].astype(str) == "outside_nyc_nearshore").to_numpy(),
        },
        loc_lat_rad=locs["lat_rad"].to_numpy(), loc_lon_rad=locs["lon_rad"].to_numpy(),
        loc_x_m=locs["x_m"].to_numpy(), loc_y_m=locs["y_m"].to_numpy(),
        loc_weight=locs["weight"].to_numpy(dtype=np.int64),
        meta={"processed_dir": str(pdir), "lineage": side["lineage"],
              "processed_content_digest": side["content_digest"], "processed_sha256": side["sha256"]},
    )


def verify_integrity(pdir: Path | None = None) -> dict[str, Any]:
    """Faz 2 sayılarını mevcut çıktılardan yeniden doğrular; uyuşmazlıkta ``AlignmentError``."""
    pdir = Path(pdir or processed_dir())
    p = pd.read_parquet(pdir / "crashes_processed.parquet",
                        columns=["collision_id", "location_id", "eligible_for_spatial_clustering",
                                 "midnight_suspect_flag", "latitude", "longitude", "lat_rad", "lon_rad", "x_m", "y_m"])
    e = p[p["eligible_for_spatial_clustering"]]
    locs = pd.read_parquet(pdir / "locations.parquet")
    feats = {n: pd.read_parquet(pdir / "features" / f"{n}.parquet") for n in (
        "A_dbscan_haversine", "A_dbscan_haversine_weighted", "B_kmeans_projected", "B_kmeans_projected_weighted",
        "C_hdbscan_haversine", "D_spatiotemporal_experimental", "D_spatiotemporal_experimental_no_midnight")}
    checks: dict[str, Any] = {}

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}

    midnight_total = int(p["midnight_suspect_flag"].sum())
    midnight_eligible = int(e["midnight_suspect_flag"].sum())
    check("collision_id_unique", p["collision_id"].is_unique, int(len(p)))
    side = json.loads((pdir / "crashes_processed.parquet.json").read_text(encoding="utf-8"))
    check("processed_rows_match_sidecar", len(p) == side["rows"], {"rows": int(len(p)), "sidecar": side["rows"]})
    for name in ("A_dbscan_haversine", "B_kmeans_projected", "C_hdbscan_haversine", "D_spatiotemporal_experimental"):
        f = feats[name]
        check(f"{name}_rows_equal_eligible", len(f) == len(e), int(len(f)))
        check(f"{name}_order_matches", bool((f["collision_id"].to_numpy() == e["collision_id"].to_numpy()).all()))
    a = feats["A_dbscan_haversine"]
    check("A_values_match_processed", np.array_equal(a["lat_rad"].to_numpy(), e["lat_rad"].to_numpy())
          and np.array_equal(a["lon_rad"].to_numpy(), e["lon_rad"].to_numpy()))
    b = feats["B_kmeans_projected"]
    check("B_values_match_processed", np.array_equal(b["x_m"].to_numpy(), e["x_m"].to_numpy()))
    check("location_ids_contiguous", np.array_equal(locs["location_id"].to_numpy(), np.arange(len(locs))), int(len(locs)))
    counts = np.bincount(e["location_id"].to_numpy(), minlength=len(locs))
    check("weights_equal_event_counts", np.array_equal(counts, locs["weight"].to_numpy()), int(locs["weight"].sum()))
    check("weighted_matrices_match_locations", all(
        np.array_equal(feats[n]["location_id"].to_numpy(), locs["location_id"].to_numpy())
        and np.array_equal(feats[n]["weight"].to_numpy(), locs["weight"].to_numpy())
        for n in ("A_dbscan_haversine_weighted", "B_kmeans_projected_weighted")))
    lid = e["location_id"].to_numpy()
    check("event_coords_equal_location_coords",
          np.array_equal(e["latitude"].to_numpy(), locs["latitude"].to_numpy()[lid])
          and np.array_equal(e["longitude"].to_numpy(), locs["longitude"].to_numpy()[lid]))
    d_nm = feats["D_spatiotemporal_experimental_no_midnight"]
    check("D_no_midnight_reconciles", len(d_nm) == len(e) - midnight_eligible,
          {"eligible": int(len(e)), "midnight_in_eligible": midnight_eligible, "D_no_midnight_rows": int(len(d_nm))})
    check("no_nan_in_features", all(not feats[n].drop(columns=[c for c in ("collision_id", "location_id")
                                                                 if c in feats[n].columns]).isna().any().any()
                                    for n in feats))
    summary = {
        "raw_rows": int(len(p)), "eligible_events": int(len(e)), "unique_locations": int(len(locs)),
        "weight_sum": int(locs["weight"].sum()), "midnight_total": midnight_total,
        "midnight_in_eligible": midnight_eligible, "midnight_outside_eligible": midnight_total - midnight_eligible,
        "D_no_midnight_rows": int(len(d_nm)), "feature_rows": {n: int(len(f)) for n, f in feats.items()},
        "checks": checks, "all_ok": all(c["ok"] for c in checks.values()),
    }
    if not summary["all_ok"]:
        raise AlignmentError(f"Hizalama kontrolleri başarısız: {[k for k, c in checks.items() if not c['ok']]}")
    return summary


# ----------------------------------------------------------------------------- alt kümeler
def subset_mask(ev: EventData, spec: dict[str, Any] | None) -> np.ndarray:
    """Alt küme tanımından olay maskesi üretir.

    Desteklenen anahtarlar: ``region`` (min/max lat/lon, derece), ``years`` (liste),
    ``exclude`` (bayrak adları: geocode_fallback, borough_conflict, nearshore, midnight),
    ``sample`` ({n, seed}: maske uygulandıktan sonra basit rastgele olay örneklemi).
    """
    spec = spec or {}
    mask = np.ones(ev.n_events, dtype=bool)
    if region := spec.get("region"):
        lat, lon = np.degrees(ev.lat_rad), np.degrees(ev.lon_rad)
        mask &= (lat >= region["min_lat"]) & (lat <= region["max_lat"]) & \
                (lon >= region["min_lon"]) & (lon <= region["max_lon"])
    if years := spec.get("years"):
        mask &= np.isin(ev.year, years)
    for flag in spec.get("exclude", []):
        if flag not in ev.flags:
            raise ValueError(f"Bilinmeyen bayrak: {flag}")
        mask &= ~ev.flags[flag]
    if sample := spec.get("sample"):
        idx = np.flatnonzero(mask)
        if sample["n"] < len(idx):
            rng = np.random.default_rng(sample["seed"])
            keep = np.sort(rng.choice(idx, size=sample["n"], replace=False))
            mask = np.zeros(ev.n_events, dtype=bool)
            mask[keep] = True
    return mask


def weighted_view(ev: EventData, mask: np.ndarray, weight_cap: float | None = None) -> dict[str, np.ndarray]:
    """Maskelenmiş olayların benzersiz konumları ve ağırlıkları.

    Dönüş: ``loc`` (konum indeksleri), ``weight`` (olay sayısı; isteğe bağlı kırpılmış),
    ``raw_weight`` (kırpılmamış), ``event_to_row`` (her maskeli olayın ``loc`` içindeki satırı).
    """
    loc_of_events = ev.location_index[mask]
    loc, inverse, counts = np.unique(loc_of_events, return_inverse=True, return_counts=True)
    weight = counts.astype(np.float64)
    if weight_cap is not None:
        weight = np.minimum(weight, weight_cap)
    return {"loc": loc, "weight": weight, "raw_weight": counts, "event_to_row": inverse.ravel()}
