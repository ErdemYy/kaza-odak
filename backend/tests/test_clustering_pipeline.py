"""Uçtan uca Faz 3: sentetik Faz 2 çıktısı üzerinde deney altyapısı (SENTETİK veri, yalnızca test)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import FakeSession, make_row
from phase2_fixtures import d, write_boundaries_snapshot
from saferoute.clustering.data import AlignmentError, verify_integrity
from saferoute.clustering.runner import Phase3Runner
from saferoute.clustering.settings import load_config
from saferoute.clustering.worker import run_isolated
from saferoute.data.download import download_snapshot, file_sha256
from saferoute.preprocess.pipeline import output_paths, run_pipeline

QUIET = {"log": lambda _: None, "sleep": lambda _: None}

TEST_CONFIG = """
[meta]
random_seed = 7
[resources]
max_neighbor_pairs = {max_pairs}
isolate_experiments = false
[equivalence]
eps_m = [40]
min_samples = [5]
city_wide_years = [2021]
city_wide_eps_m = 40
city_wide_min_samples = 5
full_records_eps_m = 40
full_records_min_samples = 5
regions = [ {{ name = "m", label = "Manhattan karesi", min_lat = 40.70, max_lat = 40.72, min_lon = -74.00, max_lon = -73.98 }} ]
[kdistance]
sample_events = 100
k_values = [5, 10]
max_unique_neighbors = 50
[dbscan]
feature_set = "A_dbscan_haversine_weighted"
eps_m = [40, 80]
min_samples = [5, 10]
[kmeans]
feature_set = "B_kmeans_projected_weighted"
k = [2, 3, 4]
n_init = 3
max_iter = 100
[hdbscan]
feature_set = "B_kmeans_projected"
sample_events = 200
min_cluster_size = [10]
min_samples = [5]
cluster_selection_method = "eom"
[evaluation]
silhouette_sample = 300
dbcv_sample = 150
[selection]
max_largest_cluster_share = 0.9
min_clusters = 2
kmeans_rule = "silhouette_common"
hdbscan_rule = "dbcv"
[temporal]
years = [2020, 2021]
grid_cell_m = 100
persistence_top_n = 2
[sensitivity]
variants = ["exclude_geocode_fallback", "exclude_borough_conflict", "exclude_nearshore", "cap_repeated_weights"]
weight_cap_percentile = 90.0
[profiles]
hull_buffer_m = 15
"""


def _rows():
    rng = np.random.default_rng(3)
    rows, cid = [], 0
    centers = [(40.710, -73.990, "MANHATTAN"), (40.712, -73.970, "BROOKLYN"), (40.708, -73.950, "QUEENS")]
    for lat0, lon0, boro in centers:
        for i in range(90):
            lat, lon = lat0 + rng.normal(0, 0.0003), lon0 + rng.normal(0, 0.0003)
            cid += 1
            rows.append(make_row(collision_id=str(cid), latitude=f"{lat:.4f}", longitude=f"{lon:.4f}",
                                 borough=boro if i % 3 else None, crash_date=d(f"{2020 + i % 2}-0{1 + i % 9}-15"),
                                 crash_time=f"{i % 24}:{i % 60:02d}", vehicle_type_code1="Sedan",
                                 number_of_persons_injured=str(i % 2), number_of_pedestrians_injured=str(i % 2)))
    for b in ("MANHATTAN", "BROOKLYN", "QUEENS"):                 # yedek geokodlama benzeri tek nokta
        cid += 1
        rows.append(make_row(collision_id=str(cid), latitude="40.7150", longitude="-73.9850", borough=b,
                             crash_date=d("2021-02-02"), crash_time="10:00"))
    for lat, lon in ((40.6995, -73.99), (40.719, -73.995), (40.701, -73.925)):   # kıyı + seyrek
        cid += 1
        rows.append(make_row(collision_id=str(cid), latitude=str(lat), longitude=str(lon), crash_date=d("2020-06-01"),
                             crash_time="3:00"))
    return rows


@pytest.fixture(scope="module")
def phase2_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p3")
    raw = download_snapshot(snapshot_dir=tmp / "raw" / "h9gi-nx95" / "snapshot_20260101T000000Z", page_size=500,
                            session=FakeSession(_rows()), **QUIET)
    bounds = write_boundaries_snapshot(tmp / "raw")
    run_pipeline(raw, bounds, interim_root=tmp / "interim", processed_root=tmp / "processed",
                 phase1_summary=tmp / "yok.json", log=lambda _: None)
    pdir = output_paths(raw.name, tmp / "interim", tmp / "processed")["processed"].parent
    return tmp, raw, pdir


def _cfg(tmp, max_pairs=10_000_000, name="phase3.toml"):
    p = tmp / name
    p.write_text(TEST_CONFIG.format(max_pairs=max_pairs), encoding="utf-8")
    return load_config(p)


def _hashes(pdir, raw):
    files = [pdir / "crashes_processed.parquet", pdir / "locations.parquet", *sorted((pdir / "features").glob("*.parquet")),
             *sorted(raw.glob("part-*.csv"))]
    return {str(f): file_sha256(f) for f in files}


@pytest.fixture(scope="module")
def run_results(phase2_env):
    tmp, raw, pdir = phase2_env
    before = _hashes(pdir, raw)
    runner = Phase3Runner(_cfg(tmp), pdir=pdir, out_dir=tmp / "out", log=lambda _: None)
    results = runner.run_all()
    return tmp, raw, pdir, runner, results, before


def test_integrity_and_alignment(run_results):
    *_, results, _ = run_results
    integ = results["integrity"]
    assert integ["all_ok"] and integ["eligible_events"] == integ["weight_sum"]
    assert integ["D_no_midnight_rows"] == integ["eligible_events"] - integ["midnight_in_eligible"]


def test_alignment_error_on_tampered_matrix(phase2_env, tmp_path):
    import shutil

    _, _, pdir = phase2_env
    copy = tmp_path / "p"
    shutil.copytree(pdir, copy)
    a = pd.read_parquet(copy / "features" / "A_dbscan_haversine.parquet")
    a.iloc[::-1].reset_index(drop=True).to_parquet(copy / "features" / "A_dbscan_haversine.parquet", index=False)
    with pytest.raises(AlignmentError, match="A_dbscan_haversine_order_matches"):
        verify_integrity(copy)


def test_weighted_equivalence_on_scenarios(run_results):
    *_, results, _ = run_results
    for s in results["equivalence"]["scenarios"]:
        assert s["records_status"] == s["weighted_status"] == "success"
        assert s["core_identical"] and s["noise_identical"] and s["core_mapping_bijective"]
        assert s["backmap_consistent"] and s["event_count_conserved"]
        assert s["differing_borders_all_adjacent_to_multiple_clusters"] in (None, True)


def test_original_data_is_unchanged(run_results):
    tmp, raw, pdir, runner, results, before = run_results
    assert _hashes(pdir, raw) == before


def test_outputs_and_count_conservation(run_results):
    tmp, raw, pdir, runner, results, _ = run_results
    sel = results["selection"]
    assert results["final_choice"]["primary_algorithm"] in ("dbscan", None)
    pts = pd.read_parquet(results["files"]["cluster_points_dbscan"])
    assert len(pts) == results["integrity"]["eligible_events"] and pts["collision_id"].is_unique
    assert set(pts["experiment_id"]) == {sel["dbscan"]}
    summ = pd.read_parquet(results["files"]["cluster_summary_dbscan"])
    assert summ["n_events"].sum() == (pts["cluster_id"] >= 0).sum()
    for col in ("experiment_id", "dataset_version", "processing_version", "parameters", "algorithm"):
        assert col in summ.columns
    geo = json.loads(open(results["files"]["cluster_geometries_dbscan"], encoding="utf-8").read())
    assert geo["metadata"]["experiment_id"] == sel["dbscan"] and "dataset_version" in geo["metadata"]
    for f in geo["features"]:
        lon, lat = f["geometry"]["coordinates"][0][0]
        assert -74.2 < lon < -73.8 and 40.6 < lat < 40.8
    meta = json.loads(open(results["files"]["model_metadata"], encoding="utf-8").read())
    assert meta["selected"]["dbscan"]["experiment_id"] == sel["dbscan"]
    comp = json.loads(open(results["files"]["algorithm_comparison"], encoding="utf-8").read())
    assert {r["algorithm"] for r in comp["rows"]} == {"dbscan", "kmeans", "hdbscan"}


def test_selection_review_and_phase4_manifest(run_results):
    import hashlib

    tmp, raw, pdir, runner, results, _ = run_results
    rows = results["selection_review"]["rows"]
    assert {r["experiment_id"] for r in rows} == set(results["selection"]["dbscan_admissible"])
    assert sum(r["selected"] for r in rows) == 1
    for r in rows:
        assert r["clustered_events"] >= r["n_clusters"] > 0
        assert 0 <= r["single_location_cluster_share"] <= 1 and r["extent_diag_m"]["max"] >= 0
    man = json.loads(open(results["files"]["phase4_manifest"], encoding="utf-8").read())
    for key, e in man["files"].items():
        path = runner.out / Path(e["path"]).name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == e["sha256"], key
    assert man["files"]["cluster_points_dbscan"]["rows"] == results["integrity"]["eligible_events"]


def test_stage_resume_recomputes_review_without_new_experiments(run_results):
    tmp, raw, pdir, runner, results, _ = run_results
    before = {r["experiment_id"]: r["created_at"] for r in runner.registry.ordered()}
    again = Phase3Runner(_cfg(tmp), pdir=pdir, out_dir=tmp / "out", log=lambda _: None)
    res = again.run_all(["review", "profiles"])
    assert res["stages_computed_this_run"] == ["review", "profiles"]
    assert res["temporal"] == results["temporal"] and res["selection"] == results["selection"]
    assert {r["experiment_id"]: r["created_at"] for r in again.registry.ordered()} == before


def test_academic_tables_are_written(run_results, tmp_path):
    from saferoute.clustering.report import temporal_interpretation, write_tables

    *_, runner, results, _ = run_results
    res = dict(results, _comparison=runner.comparison_table())
    paths = {p.name: p for p in write_tables(res, tmp_path)}
    ev = pd.read_csv(paths["evaluation_all_configs.csv"])
    assert len(ev) == len(results["evaluation"]["table"])
    assert len(pd.read_csv(paths["dbscan_selection_review.csv"])) == len(results["selection_review"]["rows"])
    assert len(pd.read_csv(paths["temporal_by_year.csv"])) == len(results["temporal"]["years"])
    ti = temporal_interpretation(results["temporal"])
    assert "scaled_jaccard_pre_median" in ti


def test_experiments_are_resumed_deterministically(run_results):
    tmp, raw, pdir, runner, results, _ = run_results
    before = {r["experiment_id"]: r["created_at"] for r in runner.registry.ordered()}
    again = Phase3Runner(_cfg(tmp), pdir=pdir, out_dir=tmp / "out", log=lambda _: None)
    again.run_all()
    after = {r["experiment_id"]: r["created_at"] for r in again.registry.ordered()}
    assert after == before                                   # aynı kimlikler, yeniden çalıştırılmadı


def test_resource_limited_experiments_are_recorded_not_faked(phase2_env):
    tmp, raw, pdir = phase2_env
    runner = Phase3Runner(_cfg(tmp, max_pairs=1, name="tiny.toml"), pdir=pdir, out_dir=tmp / "out_tiny",
                          log=lambda _: None)
    results = runner.run_all()
    grid = [runner.registry.get(i) for i in results["dbscan_grid_ids"]]
    assert all(r["status"] == "skipped_resource_limit" and "sınır" in r["error"] for r in grid)
    assert results["selection"]["dbscan"] is None and results["final_choice"]["primary_algorithm"] is None
    assert results["temporal"]["status"] == "not_run" and results["profiles"]["status"] == "not_run"
    assert all(r.get("labels_path") is None for r in grid)


def test_isolated_worker_failure_is_reported(phase2_env):
    _, _, pdir = phase2_env
    res = run_isolated({"kind": "bogus", "params": {}, "processed_dir": str(pdir), "labels_out": "x.npz"}, isolate=True)
    assert res["status"] == "failed" and "Bilinmeyen" in res["error"]
    res = run_isolated({"kind": "dbscan_weighted", "params": {"eps_m": -1, "min_samples": 5},
                        "processed_dir": str(pdir), "labels_out": "x.npz"}, isolate=False)
    assert res["status"] == "failed" and "eps_m" in res["error"]
