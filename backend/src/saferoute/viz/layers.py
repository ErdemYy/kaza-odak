"""Faz 4 coğrafi sunum katmanlarının üretimi.

Kaynak: Faz 3'ün ``phase4_manifest.json`` dosyasında listelenen çıktılar. Her dosyanın SHA-256 özeti
ve boyutu doğrulanmadan hiçbir katman üretilmez.

Üretilen katmanlar (``<processed>/phase4/``):

* ``locations_layer.parquet`` — benzersiz konum düzeyi noktalar: konum, küme kimliği, olay sayısı.
  Ağırlıklı DBSCAN'de aynı konumdaki tüm olaylar aynı etiketi alır; bu nedenle konum düzeyine
  indirgeme küme üyeliği bakımından KAYIPSIZDIR (her konum için tek etiket doğrulanır) ve olay
  toplamları kaynakla birebir eşleşir. Rastgele örnekleme veya konum üretimi yoktur.
* ``density_<hücre>m.parquet`` — UTM (EPSG:32618) kare ızgarada sunucu tarafı özet: toplam,
  kümelenmiş ve gürültü olay sayıları. Hücre toplamları kaynak toplamlarına eşittir.
* ``clusters.json`` — seçilen DBSCAN'in küme özetleri (deney kimliğiyle).
* ``cluster_geometries.geojson`` — kaynak geometrilerin doğrulanmış kopyası ([boylam, enlem]).
* ``boroughs.geojson`` — resmî ilçe sınırları (DCP gthc-hcne), görselleştirme için sadeleştirilmiş;
  kamera odakları bu sınırların gerçek sınırlayıcı kutularından hesaplanır.
* ``layer_manifest.json`` — sayılar, kaynak doğrulaması ve çıktı özetleri.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from saferoute import config

LAYER_VERSION = "4.0.0"
DENSITY_CELLS_M = (1000, 250)
# Görselleştirme sadeleştirme toleransı (derece; ~11 m). Kamera kutuları sadeleştirilmemiş sınırlardan.
BOROUGH_SIMPLIFY_DEG = 0.0001
REQUIRED_KEYS = ("cluster_points_dbscan", "cluster_summary_dbscan", "cluster_geometries_dbscan", "model_metadata",
                 "algorithm_comparison")
# NYC + kıyı payı: [boylam, enlem] sırası denetimi için kaba sınır
LON_RANGE, LAT_RANGE = (-74.6, -73.4), (40.3, 41.1)


class ManifestError(RuntimeError):
    """Faz 4 manifesti eksik, bozuk veya kaynak dosyalarla uyuşmuyor."""


class LayerConsistencyError(RuntimeError):
    """Kaynak dosyalar arasında sayı/kimlik tutarsızlığı."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_manifest_path(entry_path: str, repo_root: Path | None = None) -> Path:
    p = Path(entry_path)
    return p if p.is_absolute() else Path(repo_root or config.REPO_ROOT) / p


def verify_phase4_manifest(phase3_dir: Path, repo_root: Path | None = None) -> dict[str, Any]:
    """Manifestteki her dosyanın varlığını, boyutunu ve SHA-256 özetini doğrular; uyuşmazlıkta hata."""
    mpath = Path(phase3_dir) / "phase4_manifest.json"
    if not mpath.exists():
        raise ManifestError(f"Faz 4 manifesti bulunamadı: {mpath}")
    try:
        man = json.loads(mpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Faz 4 manifesti okunamadı: {exc}") from exc
    files = man.get("files") or {}
    missing = [k for k in REQUIRED_KEYS if k not in files]
    if missing:
        raise ManifestError(f"Manifestte gerekli kayıt yok: {missing}")
    resolved: dict[str, Any] = {}
    for key, e in files.items():
        path = resolve_manifest_path(e["path"], repo_root)
        if not path.exists():
            raise ManifestError(f"{key}: dosya yok ({path})")
        if path.stat().st_size != e["bytes"]:
            raise ManifestError(f"{key}: boyut uyuşmuyor ({path.stat().st_size} != {e['bytes']})")
        digest = sha256_file(path)
        if digest != e["sha256"]:
            raise ManifestError(f"{key}: SHA-256 uyuşmuyor")
        resolved[key] = {"path": path, "sha256": digest, "bytes": e["bytes"], "rows": e.get("rows")}
    return {"manifest_path": mpath, "manifest_sha256": sha256_file(mpath), "manifest": man, "files": resolved}


def location_layer(points: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """Olay düzeyi üyelikleri benzersiz konuma indirger; her konumun tek etiketi olduğunu doğrular."""
    g = points.groupby("location_id", sort=True)
    agg = pd.DataFrame({"cluster_id": g["cluster_id"].min(), "cluster_id_max": g["cluster_id"].max(),
                        "n_events": g.size(), "n_core": g["is_core"].sum()})
    split = agg["cluster_id"] != agg["cluster_id_max"]
    if split.any():
        raise LayerConsistencyError(f"{int(split.sum())} konumda birden fazla küme etiketi var; konum düzeyi "
                                    "indirgeme kayıpsız değil.")
    loc = locations.set_index("location_id")
    missing = agg.index.difference(loc.index)
    if len(missing):
        raise LayerConsistencyError(f"{len(missing)} konum kimliği konum tablosunda yok.")
    out = agg.drop(columns="cluster_id_max").join(loc[["longitude", "latitude", "x_m", "y_m", "borough", "weight"]])
    if not (out["n_events"] == out["weight"]).all():
        raise LayerConsistencyError("Konum olay sayıları Faz 2 konum ağırlıklarıyla uyuşmuyor.")
    out = out.drop(columns="weight").reset_index()
    out["cluster_id"] = out["cluster_id"].astype(np.int32)
    out["n_events"] = out["n_events"].astype(np.int32)
    out["n_core"] = out["n_core"].astype(np.int32)
    return out


def density_grid(layer: pd.DataFrame, cell_m: int) -> pd.DataFrame:
    """UTM kare ızgarada olay sayıları; hücre merkezi WGS84'e dönüştürülür."""
    from pyproj import Transformer

    cx = np.floor(layer["x_m"].to_numpy() / cell_m).astype(np.int64)
    cy = np.floor(layer["y_m"].to_numpy() / cell_m).astype(np.int64)
    clustered = layer["cluster_id"].to_numpy() >= 0
    n = layer["n_events"].to_numpy()
    df = pd.DataFrame({"cx": cx, "cy": cy, "events": n, "clustered": np.where(clustered, n, 0),
                       "noise": np.where(clustered, 0, n)})
    g = df.groupby(["cx", "cy"], sort=True).sum().reset_index()
    tr = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform((g["cx"].to_numpy() + 0.5) * cell_m, (g["cy"].to_numpy() + 0.5) * cell_m)
    g["longitude"], g["latitude"] = lon, lat
    return g[["cx", "cy", "longitude", "latitude", "events", "clustered", "noise"]].astype(
        {"events": np.int32, "clustered": np.int32, "noise": np.int32})


def _json_list(s: Any) -> Any:
    return json.loads(s) if isinstance(s, str) else s


def cluster_records(summary: pd.DataFrame) -> list[dict[str, Any]]:
    cols = ["cluster_id", "experiment_id", "rank_by_events", "n_events", "n_unique_locations", "centroid_lon",
            "centroid_lat", "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat", "radius_p90_m",
            "hull_area_km2", "geometry_kind", "date_min", "date_max", "active_years", "injury_crashes",
            "fatal_crashes", "persons_injured", "persons_killed", "injury_crash_share", "peak_hour",
            "dominant_borough", "dominant_borough_share", "factor_unspecified_share"]
    recs = []
    for r in summary.itertuples(index=False):
        d = {c: getattr(r, c) for c in cols}
        d = {k: (v.item() if hasattr(v, "item") else v) for k, v in d.items()}
        d = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in d.items()}  # NaN → null
        d["hour_histogram"] = [int(x) for x in r.hour_histogram]
        for c in ("top_streets", "top_contributing_factors", "top_vehicle_categories", "time_periods"):
            d[c] = _json_list(getattr(r, c))
        recs.append(d)
    return recs


def check_lon_lat_order(geojson: dict[str, Any]) -> None:
    """Tüm koordinatların [boylam, enlem] sırasında ve NYC aralığında olduğunu doğrular."""
    def walk(c: Any) -> None:
        if isinstance(c[0], (int, float)):
            lon, lat = c[0], c[1]
            if not (LON_RANGE[0] <= lon <= LON_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
                raise LayerConsistencyError(f"Koordinat [boylam, enlem] sırasında değil veya NYC dışında: {c}")
            return
        for x in c:
            walk(x)

    for f in geojson["features"]:
        walk(f["geometry"]["coordinates"])


def borough_layer() -> tuple[dict[str, Any], dict[str, Any]]:
    from saferoute.preprocess.boundaries import latest_boundaries, read_boundaries_snapshot

    gdf, man = read_boundaries_snapshot(latest_boundaries())
    bounds = {r.borough: [round(v, 6) for v in r.geometry.bounds] for r in gdf.itertuples()}
    simple = gdf.copy()
    simple["geometry"] = simple.geometry.simplify(BOROUGH_SIMPLIFY_DEG, preserve_topology=True)
    geo = json.loads(simple.to_json(drop_id=True))
    for f in geo["features"]:
        f["properties"]["bbox"] = bounds[f["properties"]["borough"]]
    source = {k: man.get(k) for k in ("dataset_id", "dataset_name", "publisher", "source_page_url", "source_version",
                                      "retrieved_at", "sha256")}
    return geo, {"bounds": bounds, "source": source, "simplify_tolerance_deg": BOROUGH_SIMPLIFY_DEG}


def _write_json(path: Path, obj: Any, indent: int | None = None) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent, default=str), encoding="utf-8")
    return path


def build_layers(pdir: Path | None = None, out_dir: Path | None = None, with_boroughs: bool = True,
                 repo_root: Path | None = None, log=print) -> dict[str, Any]:
    from saferoute.clustering.data import processed_dir

    t0 = time.perf_counter()
    pdir = Path(pdir or processed_dir())
    out = Path(out_dir or pdir / "phase4")
    out.mkdir(parents=True, exist_ok=True)
    ver = verify_phase4_manifest(pdir / "phase3", repo_root)
    f = ver["files"]
    log(f"Manifest doğrulandı: {len(f)} dosya (SHA-256 + boyut)")
    meta = json.loads(f["model_metadata"]["path"].read_text(encoding="utf-8"))
    sel = meta["selected"]["dbscan"]
    exp_id = sel["experiment_id"]
    comparison = json.loads(f["algorithm_comparison"]["path"].read_text(encoding="utf-8"))
    comp_row = next((r for r in comparison["rows"] if r["experiment_id"] == exp_id), None)
    if comp_row is None:
        raise LayerConsistencyError(f"Algoritma karşılaştırmasında seçilen deney yok: {exp_id}")

    points = pd.read_parquet(f["cluster_points_dbscan"]["path"],
                             columns=["experiment_id", "location_id", "cluster_id", "is_core"])
    exps = set(points["experiment_id"].unique())
    if exps != {exp_id}:
        raise LayerConsistencyError(f"Küme üyeliklerindeki deney kimliği {exps} seçilen {exp_id} ile aynı değil.")
    points = points.drop(columns="experiment_id")
    n_events = int(len(points))
    n_clustered = int((points["cluster_id"] >= 0).sum())
    locations = pd.read_parquet(pdir / "locations.parquet",
                                columns=["location_id", "latitude", "longitude", "x_m", "y_m", "borough", "weight"])
    layer = location_layer(points, locations)
    del points, locations

    summary = pd.read_parquet(f["cluster_summary_dbscan"]["path"])
    if set(summary["experiment_id"]) != {exp_id}:
        raise LayerConsistencyError("Küme özetinin deney kimliği seçilen deneyle aynı değil.")
    cl_ids = set(layer.loc[layer["cluster_id"] >= 0, "cluster_id"].unique().tolist())
    if set(summary["cluster_id"].tolist()) != cl_ids:
        raise LayerConsistencyError("Küme özetindeki kimlikler üyeliklerdeki kimliklerle aynı değil.")
    per_cluster = layer[layer["cluster_id"] >= 0].groupby("cluster_id")["n_events"].sum()
    if not (summary.set_index("cluster_id")["n_events"] == per_cluster.reindex(summary["cluster_id"]).values).all():
        raise LayerConsistencyError("Küme özetindeki olay sayıları üyeliklerle uyuşmuyor.")

    geo = json.loads(f["cluster_geometries_dbscan"]["path"].read_text(encoding="utf-8"))
    if geo.get("metadata", {}).get("experiment_id") != exp_id:
        raise LayerConsistencyError("Geometri dosyasının deney kimliği seçilen deneyle aynı değil.")
    if {ft["properties"]["cluster_id"] for ft in geo["features"]} != cl_ids:
        raise LayerConsistencyError("Geometri kimlikleri küme özetiyle aynı değil.")
    check_lon_lat_order(geo)

    outputs: dict[str, Path] = {}
    layer.to_parquet(out / "locations_layer.parquet", index=False)
    outputs["locations_layer"] = out / "locations_layer.parquet"
    density_meta = {}
    for cell in DENSITY_CELLS_M:
        g = density_grid(layer, cell)
        if int(g["events"].sum()) != n_events:
            raise LayerConsistencyError(f"{cell} m yoğunluk ızgarası toplamı kaynakla eşleşmiyor.")
        p = out / f"density_{cell}m.parquet"
        g.to_parquet(p, index=False)
        outputs[f"density_{cell}m"] = p
        density_meta[str(cell)] = {"cells": int(len(g)), "events": int(g["events"].sum()),
                                   "max_events_per_cell": int(g["events"].max())}
    outputs["clusters"] = _write_json(out / "clusters.json", {"experiment_id": exp_id,
                                                              "clusters": cluster_records(summary)})
    outputs["cluster_geometries"] = _write_json(out / "cluster_geometries.geojson", geo)
    boroughs_meta = None
    if with_boroughs:
        bgeo, boroughs_meta = borough_layer()
        outputs["boroughs"] = _write_json(out / "boroughs.geojson", bgeo)

    n_noise_loc = int((layer["cluster_id"] < 0).sum())
    lm = {
        "layer_version": LAYER_VERSION, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "build_seconds": None,
        "source_manifest": {"path": ver["manifest_path"].as_posix(), "sha256": ver["manifest_sha256"],
                            "verified_files": {k: {"sha256": v["sha256"], "bytes": v["bytes"]}
                                               for k, v in ver["files"].items()}},
        "dataset_version": ver["manifest"].get("dataset_version"),
        "processing_version": ver["manifest"].get("processing_version"),
        "model": {"algorithm": "dbscan", "experiment_id": exp_id, "parameters": sel["parameters"],
                  "primary_model": meta.get("primary_model"), "label_semantics": meta.get("label_semantics"),
                  "geometry_semantics": meta.get("geometry_semantics"),
                  "reported": {k: comp_row.get(k) for k in ("n_clusters_full", "noise_ratio_full",
                                                            "largest_cluster_share_full", "runtime_s")}},
        "counts": {"events_total": n_events, "events_clustered": n_clustered, "events_noise": n_events - n_clustered,
                   "noise_ratio": (n_events - n_clustered) / n_events, "clusters": len(cl_ids),
                   "locations_total": int(len(layer)), "locations_clustered": int(len(layer) - n_noise_loc),
                   "locations_noise": n_noise_loc},
        "density": density_meta, "boroughs": boroughs_meta,
        "point_reduction": "Benzersiz konum düzeyi (kayıpsız: her konumda tek etiket; olay sayısı n_events).",
    }
    if lm["counts"]["clusters"] != comp_row.get("n_clusters_full"):
        raise LayerConsistencyError("Küme sayısı Faz 3 karşılaştırma kaydıyla uyuşmuyor.")
    lm["outputs"] = {k: {"file": p.name, "sha256": sha256_file(p), "bytes": p.stat().st_size} for k, p in outputs.items()}
    lm["build_seconds"] = round(time.perf_counter() - t0, 2)
    _write_json(out / "layer_manifest.json", lm, indent=2)
    log(f"Katmanlar yazıldı: {out} ({lm['build_seconds']} sn) — {lm['counts']}")
    return lm
