"""Faz 2 işlem hattı orkestrasyonu: raw -> interim -> processed -> features.

* Ham veri yalnızca okunur; işlemden önce ve sonra SHA-256 ile doğrulanır.
* Her çıktı dosyasının yanına ``<dosya>.json`` yan kaydı yazılır: kaynak anlık görüntü
  ve SHA-256, ilçe sınırı SHA-256, yapılandırma ve özeti, hat sürümü, satır/sütun
  sayısı, dosya SHA-256 ve içerik özeti.
* İdempotent: aynı girdiler + aynı yapılandırma ile çıktılar zaten varsa ve özetleri
  doğrulanıyorsa adımlar atlanır (``force=True`` yeniden üretir; içerik özeti aynı kalır).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from saferoute import config
from saferoute.data.download import file_sha256
from saferoute.data.loader import latest_snapshot, load_raw, read_manifest, verify_snapshot
from saferoute.perf import StepTimer, peak_memory_mb
from saferoute.preprocess import casualties, coordinates, duplicates, features, geo, temporal, vehicles
from saferoute.preprocess.boundaries import latest_boundaries, read_boundaries_snapshot
from saferoute.preprocess.settings import PIPELINE_VERSION, PreprocessConfig
from saferoute.preprocess.standardize import standardize

INTERIM_NAME = "crashes_interim.parquet"
PROCESSED_NAME = "crashes_processed.parquet"
LOCATIONS_NAME = "locations.parquet"
MAPPING_NAME = "vehicle_type_mapping.parquet"
SUMMARY_NAME = "preprocessing_summary.json"


def frame_digest(df: pd.DataFrame) -> str:
    """İçerik özeti: sütun adları + türleri + satır değerlerinin hash'i (dosya baytından bağımsız)."""
    h = hashlib.sha256()
    h.update(json.dumps([(c, str(t)) for c, t in df.dtypes.items()]).encode("utf-8"))
    h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
    return h.hexdigest()


def _software() -> dict[str, str]:
    import geopandas
    import pyarrow
    import pyproj
    import shapely

    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
            "pyarrow": pyarrow.__version__, "geopandas": geopandas.__version__, "shapely": shapely.__version__,
            "pyproj": pyproj.__version__, "platform": platform.platform()}


def _write(df: pd.DataFrame, path: Path, lineage: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, path)
    meta = {
        "file": path.name, "created_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(df)), "columns": list(map(str, df.columns)), "column_count": int(df.shape[1]),
        "sha256": file_sha256(path), "content_digest": frame_digest(df), "lineage": lineage, **(extra or {}),
    }
    path.with_name(path.name + ".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str),
                                                    encoding="utf-8")
    return meta


def _sidecar_ok(path: Path, lineage_key: dict[str, Any]) -> bool:
    side = path.with_name(path.name + ".json")
    if not (path.exists() and side.exists()):
        return False
    meta = json.loads(side.read_text(encoding="utf-8"))
    key = {k: meta["lineage"].get(k) for k in lineage_key}
    return key == lineage_key and file_sha256(path) == meta["sha256"]


def output_paths(snapshot_name: str, interim_root: Path | None = None,
                 processed_root: Path | None = None) -> dict[str, Path]:
    interim = Path(interim_root or config.INTERIM_DIR) / config.DATASET_ID / snapshot_name
    processed = Path(processed_root or config.PROCESSED_DIR) / config.DATASET_ID / snapshot_name
    paths = {
        "interim": interim / INTERIM_NAME,
        "processed": processed / PROCESSED_NAME,
        "locations": processed / LOCATIONS_NAME,
        "mapping": processed / MAPPING_NAME,
        "summary": processed / SUMMARY_NAME,
    }
    for name in features.FEATURE_SETS:
        paths[f"feature:{name}"] = processed / "features" / f"{name}.parquet"
    return paths


def _phase1_crosscheck(interim: pd.DataFrame, std_stats: dict[str, Any], processed: pd.DataFrame,
                       phase1_summary: Path) -> dict[str, Any]:
    """Faz 1 raporundaki sayıları bu koşudan yeniden hesaplar ve karşılaştırır."""
    bb = config.NYC_BBOX
    lat, lon = interim["latitude"].to_numpy(), interim["longitude"].to_numpy()
    parsed = interim["coord_parse_status"].astype(str).to_numpy() == "parsed"
    zero = parsed & ((lat == 0) | (lon == 0))
    inside = (lat >= bb["min_lat"]) & (lat <= bb["max_lat"]) & (lon >= bb["min_lon"]) & (lon <= bb["max_lon"])
    valid_bbox = parsed & ~zero & inside
    borough_missing = interim["borough_original"].isna().to_numpy()
    recomputed = {
        "row_count": int(len(interim)),
        "column_count_raw": 29,
        "valid_coordinates_bbox": int(valid_bbox.sum()),
        "missing_coordinates": int((interim["coord_parse_status"].astype(str) == "missing").sum()),
        "zero_coordinates": int(zero.sum()),
        "outside_bbox": int((parsed & ~zero & ~inside).sum()),
        "borough_missing": int(borough_missing.sum()),
        "valid_bbox_borough_missing": int((valid_bbox & borough_missing).sum()),
        "distinct_valid_locations_bbox": int(pd.DataFrame({"a": lat[valid_bbox], "b": lon[valid_bbox]})
                                             .drop_duplicates().shape[0]),
        "midnight_records": int(processed["midnight_suspect_flag"].sum()),
        "vehicle_raw_distinct": std_stats["vehicle_raw_distinct"],
    }
    reference: dict[str, Any] = {}
    if phase1_summary.exists():
        p = json.loads(phase1_summary.read_text(encoding="utf-8"))["profile"]
        c = p["coordinates"]
        reference = {
            "row_count": p["schema"]["row_count"], "column_count_raw": p["schema"]["column_count"],
            "valid_coordinates_bbox": c["classes"]["valid_in_bbox"], "missing_coordinates": c["classes"]["missing"],
            "zero_coordinates": c["classes"]["zero"], "outside_bbox": c["classes"]["outside_nyc_bbox"],
            "borough_missing": p["boroughs"]["missing"], "valid_bbox_borough_missing": c["valid_but_borough_missing"],
            "distinct_valid_locations_bbox": c["distinct_valid_locations"],
            "midnight_records": p["temporal"]["crash_time_exact_midnight"],
            "vehicle_raw_distinct": p["categoricals"]["vehicle_type_distinct_raw"],
        }
    return {k: {"phase1": reference.get(k), "phase2": v, "match": reference.get(k) == v if reference else None}
            for k, v in recomputed.items()}


def run_pipeline(snapshot_dir: Path | None = None, boundaries_dir: Path | None = None,
                 cfg: PreprocessConfig | None = None, interim_root: Path | None = None,
                 processed_root: Path | None = None, force: bool = False,
                 phase1_summary: Path | None = None, log: Callable[[str], None] = print) -> dict[str, Any]:
    """Faz 2 hattını çalıştırır ve özet sözlüğünü döndürür (ayrıca JSON olarak yazar)."""
    cfg = cfg or PreprocessConfig()
    snapshot_dir = Path(snapshot_dir or latest_snapshot())
    boundaries_dir = Path(boundaries_dir or latest_boundaries())
    phase1_summary = Path(phase1_summary or config.REPORTS_DIR / "phase1" / "eda_summary.json")
    timer = StepTimer()
    t0 = time.perf_counter()

    with timer.step("verify_inputs"):
        raw_manifest = verify_snapshot(snapshot_dir)
        boroughs, b_manifest = read_boundaries_snapshot(boundaries_dir)
    lineage_key = {
        "raw_snapshot": snapshot_dir.name, "raw_combined_sha256": raw_manifest["combined_sha256"],
        "boundaries_snapshot": boundaries_dir.name, "boundaries_sha256": b_manifest["sha256"],
        "config_sha256": cfg.sha256(), "pipeline_version": PIPELINE_VERSION,
    }
    lineage = {**lineage_key, "config": cfg.as_dict(), "software": _software()}
    paths = output_paths(snapshot_dir.name, interim_root, processed_root)

    outputs = [p for k, p in paths.items() if k != "summary"]
    if not force and all(_sidecar_ok(p, lineage_key) for p in outputs) and paths["summary"].exists():
        log("Çıktılar güncel (aynı kaynak + yapılandırma); hat atlandı.")
        summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
        summary["skipped"] = True
        return summary

    with timer.step("load_raw"):
        raw = load_raw(snapshot_dir, verify=False)  # az önce doğrulandı
    with timer.step("standardize"):
        interim, std_stats = standardize(raw)
        del raw
    meta_interim = _write(interim, paths["interim"], lineage, {"layer": "interim"})
    log(f"Interim: {len(interim):,} satır ({timer.steps[-1]['seconds']} sn)")

    with timer.step("geo_borough"):
        geo_cols, geo_stats = geo.classify_coordinates(interim, boroughs, cfg)
    log(f"Coğrafi doğrulama + ilçe çıkarımı ({timer.steps[-1]['seconds']} sn)")
    with timer.step("temporal"):
        time_cols = temporal.add_temporal_features(interim, cfg)
        heaping = temporal.minute_heaping(interim)
    with timer.step("vehicles"):
        mapping = vehicles.build_mapping_table(interim)
        vehicle_cols = vehicles.add_vehicle_features(interim, mapping)
    with timer.step("casualties"):
        cas_cols = casualties.add_casualty_features(interim)
    with timer.step("coordinates"):
        valid_geo = geo_cols["is_valid_geographic_record"].to_numpy()
        lat = np.where(valid_geo, interim["latitude"].to_numpy(), np.nan)
        lon = np.where(valid_geo, interim["longitude"].to_numpy(), np.nan)
        rad = coordinates.to_radians(lat, lon)
        x, y = coordinates.project(lat, lon, cfg.projected_crs, cfg.geographic_crs)
        x, y = np.where(valid_geo, x, np.nan), np.where(valid_geo, y, np.nan)  # pyproj NaN girdiye inf dönebilir
        coord_cols = pd.DataFrame({"lat_rad": rad[:, 0], "lon_rad": rad[:, 1], "x_m": x, "y_m": y},
                                  index=interim.index)
        eligible = geo_cols["eligible_for_spatial_clustering"].to_numpy()
        coord_cols["location_id"] = duplicates.assign_location_ids(interim["latitude"].to_numpy(),
                                                                    interim["longitude"].to_numpy(), eligible)
        proj_check = coordinates.projection_check(interim["latitude"].to_numpy()[eligible],
                                                  interim["longitude"].to_numpy()[eligible], cfg.projected_crs)
    processed = pd.concat([interim, geo_cols, time_cols, vehicle_cols, cas_cols, coord_cols], axis=1)
    assert len(processed) == len(interim) == raw_manifest["row_count"], "satır sayısı korunmalı"
    geo_stats["conflict_analysis"] = geo.conflict_analysis(processed, boroughs, cfg)
    fallback_cols, geo_stats["geocode_fallback"] = duplicates.geocode_fallback_flags(processed)
    processed = pd.concat([processed, fallback_cols], axis=1)
    meta_processed = _write(processed, paths["processed"], lineage, {"layer": "processed"})
    _write(mapping, paths["mapping"], lineage, {"layer": "reference"})
    log(f"Processed: {len(processed):,} satır, {processed.shape[1]} sütun")

    with timer.step("locations_features"):
        locs = duplicates.location_table(processed)
        rad_l = coordinates.to_radians(locs["latitude"], locs["longitude"])
        locs["lat_rad"], locs["lon_rad"] = rad_l[:, 0], rad_l[:, 1]
        locs["x_m"], locs["y_m"] = coordinates.project(locs["latitude"].to_numpy(), locs["longitude"].to_numpy(),
                                                       cfg.projected_crs, cfg.geographic_crs)
        _write(locs, paths["locations"], lineage, {"layer": "processed"})
        sets = features.build_feature_sets(processed, locs)
        feature_meta = {}
        for name, frame in sets.items():
            feature_meta[name] = _write(frame, paths[f"feature:{name}"], lineage,
                                        {"layer": "features", "spec": features.FEATURE_SETS[name]})
        repetition = duplicates.repetition_analysis(processed, locs, cfg.top_repeated_locations)

    with timer.step("verify_raw_unchanged"):
        raw_after = verify_snapshot(snapshot_dir)
        _, b_after = read_boundaries_snapshot(boundaries_dir)
    raw_unchanged = (raw_after["combined_sha256"] == raw_manifest["combined_sha256"]
                     and b_after["sha256"] == b_manifest["sha256"])

    summary = build_summary(interim, processed, std_stats, geo_stats, heaping, mapping, repetition, proj_check,
                            sets, raw_manifest, b_manifest, lineage, timer, t0, raw_unchanged,
                            {"interim": meta_interim, "processed": meta_processed, "features": feature_meta},
                            _phase1_crosscheck(interim, std_stats, processed, phase1_summary))
    paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log(f"Tamamlandı ({summary['runtime']['total_seconds']} sn, bellek tepe {summary['runtime']['peak_memory_mb']} MB)")
    return summary


def _counts(s: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}


def build_summary(interim, processed, std_stats, geo_stats, heaping, mapping, repetition, proj_check, sets,
                  raw_manifest, b_manifest, lineage, timer, t0, raw_unchanged, file_meta, crosscheck) -> dict[str, Any]:
    n = len(processed)
    status = processed["coordinate_quality_status"]
    orig_missing = processed["borough_original"].isna()
    conflicts = processed[processed["borough_conflict_flag"]]
    pair_counts = conflicts.groupby(["borough_original", "borough_inferred"], observed=True).size()
    eligible = processed["eligible_for_spatial_clustering"]
    vcat1 = processed["vehicle_category_1"].astype(object).where(processed["vehicle_category_1"].notna(), "(boş)")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skipped": False,
        "lineage": lineage,
        "raw_unchanged": bool(raw_unchanged),
        "boundaries": {k: b_manifest[k] for k in ("dataset_id", "source_version", "publication_date", "rows_updated_at",
                                                   "declared_crs", "sha256", "bytes", "validation", "retrieved_at")},
        "rows": {"raw": raw_manifest["row_count"], "interim": int(len(interim)), "processed": n,
                 "eligible_for_spatial_clustering": int(eligible.sum()),
                 "is_valid_geographic_record": int(processed["is_valid_geographic_record"].sum())},
        "standardize": std_stats,
        "coordinates": {
            "status_counts": {k: int(v) for k, v in status.value_counts().reindex(geo.COORD_STATUSES, fill_value=0).items()},
            "exclusion_reason_counts": _counts(processed["exclusion_reason"].astype(str)),
            "distance_outside_nyc_m": {
                "count": int(processed["distance_outside_nyc_m"].notna().sum()),
                **{f"p{q}": float(processed["distance_outside_nyc_m"].quantile(q / 100)) for q in (50, 90, 95, 99)},
                "max": float(processed["distance_outside_nyc_m"].max()) if processed["distance_outside_nyc_m"].notna().any() else None,
                "cumulative_within_m": {str(t): int((processed["distance_outside_nyc_m"] <= t).sum())
                                        for t in (25, 50, 100, 200, 300, 500, 1000, 5000)},
            },
            "overlapping_reasons": {
                "coordinate_invalid_and_borough_missing": int((~processed["is_valid_geographic_record"] & orig_missing).sum()),
                "coordinate_invalid_and_midnight_suspect": int((~processed["is_valid_geographic_record"]
                                                                & processed["midnight_suspect_flag"]).sum()),
                "coordinate_invalid_and_injury_flagged": int((~processed["is_valid_geographic_record"]
                                                              & (processed["injury_data_quality_flag"] != "ok")).sum()),
            },
            **geo_stats,
            "projection_check": proj_check,
        },
        "boroughs": {
            "original_counts": _counts(processed["borough_original"].astype(object).fillna("(eksik)")),
            "final_counts": _counts(processed["borough_final"].astype(object).fillna("(eksik)")),
            "inferred_counts": _counts(processed["borough_inferred"].astype(object).fillna("(çıkarılamadı)")),
            "source_counts": _counts(processed["borough_source"].astype(str)),
            "inference_status_counts": _counts(processed["borough_inference_status"].astype(str)),
            "original_missing": int(orig_missing.sum()),
            "recovered_by_polygon": int((processed["borough_source"] == "inferred_polygon").sum()),
            "still_missing": int(processed["borough_final"].isna().sum()),
            "still_missing_by_reason": _counts(processed.loc[processed["borough_final"].isna(),
                                                             "borough_inference_status"].astype(str)),
            "outside_polygons": int((processed["borough_inference_status"] == "outside_polygons").sum()),
            "conflicts": int(len(conflicts)),
            "conflict_pct_of_comparable": round(100.0 * len(conflicts) / max(1, int(((~orig_missing)
                                                & processed["borough_inferred"].notna()).sum())), 4),
            "comparable_original_and_inferred": int(((~orig_missing) & processed["borough_inferred"].notna()).sum()),
            "conflict_pairs": {f"{a} -> {b}": int(v) for (a, b), v in pair_counts.sort_values(ascending=False).items()},
        },
        "temporal": {
            "midnight_suspect": int(processed["midnight_suspect_flag"].sum()),
            "midnight_suspect_pct": round(100.0 * processed["midnight_suspect_flag"].sum() / n, 4) if n else 0.0,
            "minute_heaping": heaping,
            "time_period_counts": _counts(processed["time_period"].astype(str)),
            "weekend_records": int(processed["is_weekend"].fillna(False).sum()),
            "hour_counts": {str(k): int(v) for k, v in processed["crash_hour"].value_counts().sort_index().items()},
        },
        "vehicles": {**vehicles.mapping_summary(mapping, std_stats["vehicle_raw_distinct"]),
                     "vehicle_category_1_counts": _counts(vcat1),
                     "involves_counts": {c: int(processed[c].sum()) for c in processed.columns if c.startswith("involves_")}},
        "casualties": casualties.casualty_summary(interim, processed),
        "repetition": repetition,
        "feature_sets": features.feature_set_summary(sets),
        "files": file_meta,
        "phase1_crosscheck": crosscheck,
        "runtime": {"steps": timer.steps, "total_seconds": round(time.perf_counter() - t0, 2),
                    "peak_memory_mb": peak_memory_mb(), "cpu_count": os.cpu_count()},
    }
