"""Faz 4 coğrafi katmanları ve API'si: manifest bütünlüğü, kimlik eşleşmesi, sayı tutarlılığı, bbox sorguları."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from saferoute.viz.layers import (
    LayerConsistencyError, ManifestError, build_layers, check_lon_lat_order, location_layer, verify_phase4_manifest,
)

EXP = "dbscan-test000001"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _hull(lon: float, lat: float, d: float = 0.0002) -> list:
    return [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]]


def make_phase3(root: Path) -> Path:
    """Gerçek Faz 3 dosya düzeninde küçük bir örnek: 3 küme, 12 konum, 60 olay (gürültü dahil)."""
    pdir = root / "processed"
    p3 = pdir / "phase3"
    p3.mkdir(parents=True)
    rng = np.random.default_rng(0)
    # 12 konum: Manhattan (0-5), Brooklyn (6-9), gürültü (10-11 + 3 ve 8 numaralı gürültü konumları)
    lons = np.array([-73.9851, -73.9852, -73.9850, -73.9700, -73.9701, -73.9702,
                     -73.9845, -73.9846, -73.9500, -73.9501, -73.9300, -74.1500])
    lats = np.array([40.7589, 40.7590, 40.7588, 40.7600, 40.7601, 40.7602,
                     40.6960, 40.6961, 40.6800, 40.6801, 40.7200, 40.5800])
    labels = np.array([0, 0, 0, -1, 1, 1, 2, 2, -1, -1, -1, -1])
    weights = np.array([10, 8, 6, 2, 7, 5, 9, 4, 1, 3, 2, 3])
    locs = pd.DataFrame({"location_id": np.arange(12), "latitude": lats, "longitude": lons, "weight": weights,
                         "borough": ["MANHATTAN"] * 6 + ["BROOKLYN"] * 4 + ["QUEENS", "STATEN ISLAND"],
                         "x_m": (lons + 74) * 84000, "y_m": (lats - 40) * 111000 + 4.5e6})
    locs.to_parquet(pdir / "locations.parquet", index=False)
    loc_ids = np.repeat(np.arange(12), weights)
    pts = pd.DataFrame({"experiment_id": EXP, "algorithm": "dbscan", "collision_id": np.arange(len(loc_ids)) + 1000,
                        "location_id": loc_ids, "cluster_id": labels[loc_ids].astype(np.int32),
                        "is_core": rng.random(len(loc_ids)) > 0.3})
    pts.to_parquet(p3 / "cluster_points_dbscan.parquet", index=False)
    rows = []
    for cid in (0, 1, 2):
        m = labels == cid
        rows.append({"experiment_id": EXP, "algorithm": "dbscan", "dataset_version": "dv", "processing_version": "pv",
                     "parameters": json.dumps({"eps_m": 25, "min_samples": 5}), "rank_by_events": 0, "cluster_id": cid,
                     "n_events": int(weights[m].sum()), "n_unique_locations": int(m.sum()),
                     "centroid_lon": float(np.average(lons[m], weights=weights[m])),
                     "centroid_lat": float(np.average(lats[m], weights=weights[m])),
                     "bbox_min_lon": float(lons[m].min()), "bbox_min_lat": float(lats[m].min()),
                     "bbox_max_lon": float(lons[m].max()), "bbox_max_lat": float(lats[m].max()), "radius_p90_m": 9.5,
                     "hull_area_km2": float("nan") if cid == 2 else 0.001, "geometry_kind": "convex_hull",
                     "events_per_km2_hull": 1.0, "date_min": "2013-01-01", "date_max": "2025-12-31", "active_years": 13,
                     "injury_crashes": 3, "fatal_crashes": 0, "persons_injured": 4, "persons_killed": 0,
                     "injury_crash_share": 0.2, "hour_histogram": np.arange(24), "peak_hour": 23,
                     "dominant_borough": None if cid == 2 else "MANHATTAN", "dominant_borough_share": None if cid == 2 else 1.0,
                     "top_vehicle_categories": "[]", "top_contributing_factors": "[]", "time_periods": "[]",
                     "top_streets": json.dumps([{"value": "BROADWAY", "count": 3, "share": 0.5}]),
                     "factor_unspecified_share": 0.1})
    s = pd.DataFrame(rows).sort_values("n_events", ascending=False)
    s["rank_by_events"] = np.arange(1, 4)
    s.to_parquet(p3 / "cluster_summary_dbscan.parquet", index=False)
    geo = {"type": "FeatureCollection", "metadata": {"experiment_id": EXP},
           "features": [{"type": "Feature", "properties": {"cluster_id": r["cluster_id"], "experiment_id": EXP},
                         "geometry": {"type": "Polygon", "coordinates": _hull(r["centroid_lon"], r["centroid_lat"])}}
                        for r in rows]}
    (p3 / "cluster_geometries_dbscan.geojson").write_text(json.dumps(geo), encoding="utf-8")
    (p3 / "model_metadata.json").write_text(json.dumps({
        "selected": {"dbscan": {"experiment_id": EXP, "parameters": {"eps_m": 25, "min_samples": 5}}},
        "primary_model": "dbscan", "label_semantics": "-1 = gürültü", "geometry_semantics": "zarf"}), encoding="utf-8")
    (p3 / "algorithm_comparison.json").write_text(json.dumps({"rows": [
        {"algorithm": "dbscan", "experiment_id": EXP, "n_clusters_full": 3, "noise_ratio_full": 0.18,
         "largest_cluster_share_full": 0.4, "runtime_s": 0.1}]}), encoding="utf-8")
    files = {}
    for key, name in (("cluster_points_dbscan", "cluster_points_dbscan.parquet"),
                      ("cluster_summary_dbscan", "cluster_summary_dbscan.parquet"),
                      ("cluster_geometries_dbscan", "cluster_geometries_dbscan.geojson"),
                      ("model_metadata", "model_metadata.json"), ("algorithm_comparison", "algorithm_comparison.json")):
        f = p3 / name
        files[key] = {"path": f.as_posix(), "sha256": _sha(f), "bytes": f.stat().st_size, "rows": None}
    (p3 / "phase4_manifest.json").write_text(json.dumps({"dataset_version": "dv", "processing_version": "pv",
                                                          "files": files}), encoding="utf-8")
    return pdir


@pytest.fixture()
def built(tmp_path):
    pdir = make_phase3(tmp_path)
    lm = build_layers(pdir, with_boroughs=False, log=lambda _: None)
    return pdir, lm


# ----------------------------------------------------------------------------- manifest ve tutarlılık
def test_manifest_hashes_are_verified(tmp_path):
    pdir = make_phase3(tmp_path)
    ver = verify_phase4_manifest(pdir / "phase3")
    assert set(ver["files"]) >= {"cluster_points_dbscan", "model_metadata"}
    with open(pdir / "phase3" / "model_metadata.json", "a", encoding="utf-8") as f:
        f.write(" ")  # tek bayt değişiklik: boyut ve özet uyuşmaz
    with pytest.raises(ManifestError, match="model_metadata"):
        verify_phase4_manifest(pdir / "phase3")


def test_manifest_missing_or_tampered_hash(tmp_path):
    pdir = make_phase3(tmp_path)
    m = json.loads((pdir / "phase3" / "phase4_manifest.json").read_text(encoding="utf-8"))
    m["files"]["cluster_points_dbscan"]["sha256"] = "0" * 64
    (pdir / "phase3" / "phase4_manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ManifestError, match="SHA-256"):
        build_layers(pdir, with_boroughs=False, log=lambda _: None)
    (pdir / "phase3" / "phase4_manifest.json").unlink()
    with pytest.raises(ManifestError, match="bulunamadı"):
        verify_phase4_manifest(pdir / "phase3")


def test_counts_are_conserved(built):
    pdir, lm = built
    c = lm["counts"]
    assert c["events_total"] == 60 and c["events_clustered"] == 10 + 8 + 6 + 7 + 5 + 9 + 4
    assert c["events_noise"] == c["events_total"] - c["events_clustered"]
    assert c["clusters"] == 3 and c["locations_total"] == 12
    layer = pd.read_parquet(pdir / "phase4" / "locations_layer.parquet")
    assert layer["n_events"].sum() == c["events_total"]
    for cell, d in lm["density"].items():
        g = pd.read_parquet(pdir / "phase4" / f"density_{cell}m.parquet")
        assert g["events"].sum() == c["events_total"] == d["events"]
        assert (g["clustered"] + g["noise"] == g["events"]).all()


def test_location_reduction_is_lossless_and_rejects_split_labels(tmp_path):
    pts = pd.DataFrame({"location_id": [0, 0, 1], "cluster_id": [1, 1, -1], "is_core": [True, False, False]})
    locs = pd.DataFrame({"location_id": [0, 1], "latitude": [40.7, 40.71], "longitude": [-73.9, -73.91],
                         "x_m": [0.0, 1.0], "y_m": [0.0, 1.0], "borough": ["MANHATTAN"] * 2, "weight": [2, 1]})
    out = location_layer(pts, locs)
    assert out["n_events"].tolist() == [2, 1] and out["cluster_id"].tolist() == [1, -1]
    with pytest.raises(LayerConsistencyError, match="birden fazla küme"):
        location_layer(pts.assign(cluster_id=[1, 2, -1]), locs)
    with pytest.raises(LayerConsistencyError, match="ağırlık"):
        location_layer(pts, locs.assign(weight=[3, 1]))


def test_experiment_id_mismatch_is_rejected(tmp_path):
    pdir = make_phase3(tmp_path)
    p = pdir / "phase3" / "cluster_points_dbscan.parquet"
    pd.read_parquet(p).assign(experiment_id="kmeans-xyz").to_parquet(p, index=False)
    m = json.loads((pdir / "phase3" / "phase4_manifest.json").read_text(encoding="utf-8"))
    m["files"]["cluster_points_dbscan"].update(sha256=_sha(p), bytes=p.stat().st_size)
    (pdir / "phase3" / "phase4_manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(LayerConsistencyError, match="deney kimliği"):
        build_layers(pdir, with_boroughs=False, log=lambda _: None)


def test_geojson_coordinate_order_lon_lat(built):
    pdir, _ = built
    geo = json.loads((pdir / "phase4" / "cluster_geometries.geojson").read_text(encoding="utf-8"))
    check_lon_lat_order(geo)  # hata yok
    for f in geo["features"]:
        lon, lat = f["geometry"]["coordinates"][0][0]
        assert -75 < lon < -73 and 40 < lat < 41
    swapped = {"features": [{"geometry": {"coordinates": [[[40.7, -73.9]]]}}]}
    with pytest.raises(LayerConsistencyError, match="boylam, enlem"):
        check_lon_lat_order(swapped)


def test_cluster_records_are_json_safe(built):
    pdir, _ = built
    text = (pdir / "phase4" / "clusters.json").read_text(encoding="utf-8")
    assert "NaN" not in text
    c = {r["cluster_id"]: r for r in json.loads(text)["clusters"]}
    assert c[2]["hull_area_km2"] is None and c[2]["dominant_borough"] is None


# ----------------------------------------------------------------------------- API
@pytest.fixture()
def client(built):
    from fastapi.testclient import TestClient

    from saferoute.viz.api import create_app

    pdir, lm = built
    return TestClient(create_app(pdir / "phase4")), lm


def test_meta_reads_real_values(client):
    c, lm = client
    m = c.get("/api/meta").json()
    assert m["model"]["experiment_id"] == EXP and m["model"]["parameters"] == {"eps_m": 25, "min_samples": 5}
    assert m["counts"] == lm["counts"]


def test_cluster_detail_and_id_matching(client):
    c, _ = client
    for cid in (0, 1, 2):
        d = c.get(f"/api/clusters/{cid}", params={"experiment_id": EXP}).json()
        assert d["cluster_id"] == cid and d["experiment_id"] == EXP
    assert c.get("/api/clusters/1", params={"experiment_id": "kmeans-24c07e9946"}).status_code == 409
    assert c.get("/api/clusters/99").status_code == 404
    feats = c.get("/api/clusters").json()["features"]
    assert sorted(f["properties"]["cluster_id"] for f in feats) == [0, 1, 2]
    for f in feats:  # merkez noktası özetle aynı
        d = c.get(f"/api/clusters/{f['properties']['cluster_id']}").json()
        assert f["geometry"]["coordinates"] == [d["centroid_lon"], d["centroid_lat"]]
        assert f["properties"]["n_events"] == d["n_events"]


def test_points_bbox_query_and_counts(client):
    c, lm = client
    bbox = "-73.99,40.755,-73.965,40.765"  # Manhattan örnek kümeleri + 1 gürültü konumu
    r = c.get("/api/points", params={"bbox": bbox}).json()
    assert r["total_locations"] == 6 and r["total_events"] == 38 and not r["truncated"]
    for f in r["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert -73.99 <= lon <= -73.965 and 40.755 <= lat <= 40.765
    noise = c.get("/api/points", params={"bbox": bbox, "kind": "noise"}).json()
    clustered = c.get("/api/points", params={"bbox": bbox, "kind": "clustered"}).json()
    assert noise["total_events"] + clustered["total_events"] == r["total_events"]
    assert all(f["properties"]["noise"] for f in noise["features"])
    assert all(f["properties"]["cluster_id"] >= 0 for f in clustered["features"])
    lim = c.get("/api/points", params={"bbox": bbox, "limit": 2}).json()
    assert lim["truncated"] and lim["returned_locations"] == 2 and lim["total_events"] == 38
    assert [f["properties"]["n_events"] for f in lim["features"]] == [10, 8]  # deterministik: en yoğun önce


def test_points_input_validation_and_limits(client):
    c, _ = client
    assert c.get("/api/points", params={"bbox": "-74.3,40.4,-73.6,41"}).status_code == 413  # büyük alan
    assert c.get("/api/points", params={"bbox": "1,2,3"}).status_code == 422
    assert c.get("/api/points", params={"bbox": "-73.9,40.7,-74.0,40.8"}).status_code == 422  # batı > doğu
    assert c.get("/api/points", params={"bbox": "nan,40.7,-73.9,40.8"}).status_code == 422
    assert c.get("/api/points", params={"bbox": "-73.99,40.755,-73.965,40.765", "limit": 10**6}).status_code == 422
    assert c.get("/api/points", params={"bbox": "-73.99,40.755,-73.965,40.765", "kind": "x"}).status_code == 422
    assert c.get("/api/density", params={"cell": 7}).status_code == 422


def test_density_and_geometry_filters(client):
    c, lm = client
    d = c.get("/api/density", params={"cell": 1000}).json()
    assert d["total_events"] == lm["counts"]["events_total"]
    g = c.get("/api/clusters/geometries", params={"bbox": "-73.99,40.69,-73.98,40.70"}).json()
    assert [f["properties"]["cluster_id"] for f in g["features"]] == [2]


def _real_layers() -> Path | None:
    try:
        from saferoute.clustering.data import processed_dir

        p = processed_dir() / "phase4"
    except Exception:
        return None
    return p if (p / "layer_manifest.json").exists() else None


@pytest.mark.skipif(_real_layers() is None, reason="Gerçek Faz 4 katmanları üretilmemiş (saferoute viz-build)")
def test_real_layers_match_phase3_records():
    """Gerçek veri: katman sayıları Faz 3 kayıtlarıyla (karşılaştırma tablosu, manifest, üyelikler) birebir."""
    from saferoute.viz.layers import sha256_file

    p4 = _real_layers()
    lm = json.loads((p4 / "layer_manifest.json").read_text(encoding="utf-8"))
    p3 = p4.parent / "phase3"
    comp = json.loads((p3 / "algorithm_comparison.json").read_text(encoding="utf-8"))
    row = next(r for r in comp["rows"] if r["experiment_id"] == lm["model"]["experiment_id"])
    assert lm["counts"]["clusters"] == row["n_clusters_full"]
    assert abs(lm["counts"]["noise_ratio"] - row["noise_ratio_full"]) < 1e-12
    man = json.loads((p3 / "phase4_manifest.json").read_text(encoding="utf-8"))
    assert lm["source_manifest"]["sha256"] == sha256_file(p3 / "phase4_manifest.json")
    assert man["files"]["cluster_points_dbscan"]["rows"] == lm["counts"]["events_total"]
    for key, o in lm["outputs"].items():
        assert sha256_file(p4 / o["file"]) == o["sha256"], key
    layer = pd.read_parquet(p4 / "locations_layer.parquet", columns=["cluster_id", "n_events"])
    assert int(layer["n_events"].sum()) == lm["counts"]["events_total"]
    assert int(layer.loc[layer["cluster_id"] >= 0, "n_events"].sum()) == lm["counts"]["events_clustered"]
    assert layer.loc[layer["cluster_id"] >= 0, "cluster_id"].nunique() == lm["counts"]["clusters"]


def test_tampered_layer_file_blocks_server(built):
    from saferoute.viz.api import create_app

    pdir, _ = built
    with open(pdir / "phase4" / "clusters.json", "a", encoding="utf-8") as f:
        f.write(" ")
    with pytest.raises(RuntimeError, match="SHA-256"):
        create_app(pdir / "phase4")
