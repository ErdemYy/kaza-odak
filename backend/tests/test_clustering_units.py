"""Faz 3 birim testleri: algoritma sarmalayıcıları, değerlendirme, kayıt ve geometri (SENTETİK veri)."""

import json

import numpy as np
import pandas as pd
import pytest

from saferoute.clustering import algorithms as alg
from saferoute.clustering import evaluation as E
from saferoute.clustering.profiling import cluster_profiles
from saferoute.clustering.registry import ExperimentRecord, Registry, experiment_id
from saferoute.clustering.settings import ConfigError, load_config
from saferoute.preprocess.coordinates import EARTH_RADIUS_M, haversine_m, project, to_radians


def _pts(lat, lon):
    return to_radians(np.asarray(lat, float), np.asarray(lon, float))


# ---------------------------------------------------------------- eps dönüşümü ve metrik
def test_eps_meters_are_converted_to_radians():
    lat = [40.7000, 40.7000 + 90 / 111_195.08]                 # ~90 m kuzey
    X = _pts(lat, [-73.99, -73.99])
    assert haversine_m(lat[0], -73.99, lat[1], -73.99) == pytest.approx(90, rel=1e-3)
    same = alg.dbscan_haversine(X, eps_m=100, min_samples=2)
    apart = alg.dbscan_haversine(X, eps_m=80, min_samples=2)
    assert same["labels"].tolist() == [0, 0]
    assert apart["labels"].tolist() == [-1, -1]


def test_degree_input_is_rejected_as_non_radian():
    with pytest.raises(alg.InvalidParameter, match="radyan"):
        alg.dbscan_haversine(np.array([[40.7, -73.99], [40.71, -73.98]]), 100, 2)


@pytest.mark.parametrize("eps,ms", [(0, 5), (-10, 5), (float("nan"), 5), (True, 5), ("100", 5), (100, 0), (100, 2.5),
                                    (100, True)])
def test_invalid_dbscan_parameters(eps, ms):
    with pytest.raises(alg.InvalidParameter):
        alg.validate_dbscan(eps, ms)


@pytest.mark.parametrize("mcs,ms", [(1, 5), (0, None), (True, 5), (10, 0)])
def test_invalid_hdbscan_parameters(mcs, ms):
    with pytest.raises(alg.InvalidParameter):
        alg.validate_hdbscan(mcs, ms)


def test_invalid_kmeans_parameters():
    with pytest.raises(alg.InvalidParameter):
        alg.validate_kmeans(1, 10)
    with pytest.raises(alg.InvalidParameter):
        alg.validate_kmeans(11, 10)


# ---------------------------------------------------------------- ağırlıklı DBSCAN
def test_weight_alone_makes_a_core_point():
    X = _pts([40.70, 40.75], [-73.99, -73.90])                 # birbirinden uzak iki konum
    r = alg.dbscan_haversine(X, 50, min_samples=10, sample_weight=np.array([10, 9]))
    assert r["core_mask"].tolist() == [True, False]
    assert r["labels"].tolist() == [0, -1]


def _duplicated_sample(seed=0):
    rng = np.random.default_rng(seed)
    base = np.vstack([c + rng.normal(0, 0.0004, (60, 2)) for c in ([40.70, -73.99], [40.705, -73.985], [40.75, -73.95])])
    base = np.round(base, 4)                                   # yuvarlama -> tekrarlı koordinatlar
    pts = np.vstack([base, base[:40], base[:10], [[40.80, -73.90]]])
    return to_radians(pts[:, 0], pts[:, 1])


def test_weighted_and_record_level_cores_and_noise_are_identical():
    X = _duplicated_sample()
    uniq, inv, w = np.unique(X, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    for eps, ms in ((40, 5), (80, 12), (150, 30)):
        rec = alg.dbscan_haversine(X, eps, ms)
        wtd = alg.dbscan_haversine(uniq, eps, ms, sample_weight=w)
        cmp = E.compare_partitions(rec["labels"], rec["core_mask"], wtd["labels"][inv], wtd["core_mask"][inv], X,
                                   eps / EARTH_RADIUS_M)
        assert cmp["core_identical"] and cmp["noise_identical"], (eps, ms)
        assert cmp["core_partition_ari"] in (None, 1.0) and cmp["core_mapping_bijective"]
        assert cmp["differing_borders_all_adjacent_to_multiple_clusters"] in (None, True)
        assert len(wtd["labels"][inv]) == len(X)              # olay sayısı korunur


def test_label_mapping_is_permutation_invariant():
    a = np.array([0, 0, 1, 1, 2, -1])
    b = np.array([7, 7, 3, 3, 5, -1])                          # aynı bölümleme, farklı numaralar
    assert E.ari(a, b) == 1.0
    core = np.array([True, True, True, True, True, False])
    X = _pts([40.70, 40.70, 40.71, 40.71, 40.72, 40.8], [-73.99] * 6)
    cmp = E.compare_partitions(a, core, b, core, X, 1e-6)
    assert cmp["core_mapping_bijective"] and cmp["core_partition_ari"] == 1.0
    split = np.array([0, 1, 1, 1, 2, -1])                      # farklı bölümleme
    assert not E.compare_partitions(a, core, split, core, X, 1e-6)["core_mapping_bijective"]


def test_resource_limit_is_enforced_before_fit():
    X = _duplicated_sample()
    with pytest.raises(alg.ResourceLimitExceeded, match="sınır"):
        alg.dbscan_haversine(X, 150, 5, max_neighbor_pairs=10)


# ---------------------------------------------------------------- K-Means / HDBSCAN
def test_kmeans_weighted_objective_equals_duplicated_and_is_deterministic():
    """Ağırlıklı K-Means'in amaç fonksiyonu (atalet), aynı merkezler için tekrarlı veriyle birebir aynıdır."""
    rng = np.random.default_rng(1)
    uniq = rng.normal(0, 100, (40, 2))
    w = rng.integers(1, 6, size=40)
    dup = np.repeat(uniq, w, axis=0)                           # her konum w kez tekrarlanır
    wtd = alg.kmeans_projected(uniq, 4, w, n_init=5, max_iter=300, seed=42)
    again = alg.kmeans_projected(uniq, 4, w, n_init=5, max_iter=300, seed=42)
    assert np.array_equal(wtd["labels"], again["labels"])     # sabit tohum -> deterministik
    labels_dup = np.repeat(wtd["labels"], w)
    inertia_dup = float(((dup - wtd["centers"][labels_dup]) ** 2).sum())
    assert wtd["inertia"] == pytest.approx(inertia_dup, rel=1e-9)


def test_hdbscan_runs_and_marks_noise():
    rng = np.random.default_rng(2)
    Y = np.vstack([rng.normal(0, 5, (40, 2)), rng.normal(500, 5, (40, 2)), [[5000, 5000]]])
    r = alg.hdbscan_projected(Y, min_cluster_size=10, min_samples=5)
    assert r["labels"][-1] == -1 and len(set(r["labels"][:80])) == 2
    assert ((r["probabilities"] >= 0) & (r["probabilities"] <= 1)).all()


# ---------------------------------------------------------------- değerlendirme
def test_cluster_stats_and_noise_handling():
    s = E.cluster_stats(np.array([0, 0, 1, -1, -1]), weights=np.array([3, 1, 2, 2, 2]))
    assert s["n_clusters"] == 2 and s["n_events"] == 10 and s["noise_events"] == 4
    assert s["noise_ratio"] == pytest.approx(0.4) and s["largest_cluster_share"] == pytest.approx(0.4)
    assert s["clustered_events"] + s["noise_events"] == s["n_events"]


def test_silhouette_validity_rules():
    X = np.random.default_rng(0).normal(size=(30, 2))
    assert E.silhouette(X, np.full(30, -1), "euclidean", 100, 0)["status"] == "N/A"
    assert E.silhouette(X, np.r_[np.zeros(25), -np.ones(5)].astype(int), "euclidean", 100, 0)["status"] == "N/A"
    assert E.davies_bouldin(X, np.zeros(30, int), 100, 0)["status"] == "N/A"
    labels = np.r_[np.zeros(12), np.ones(12), -np.ones(6)].astype(int)
    X2 = np.vstack([np.random.default_rng(1).normal(0, 1, (12, 2)), np.random.default_rng(2).normal(20, 1, (12, 2)),
                    np.random.default_rng(3).normal(10, 30, (6, 2))])
    r = E.silhouette(X2, labels, "euclidean", 100, 0)
    assert r["status"] == "ok" and r["n_used"] == 24 and r["noise_excluded_ratio"] == pytest.approx(0.2)
    assert r["value"] > 0.8


def test_stratified_sample_is_seeded_and_proportional():
    labels = np.r_[np.zeros(900), np.ones(100), -np.ones(500)].astype(int)
    a = E.stratified_sample(labels, 100, seed=7)
    assert np.array_equal(a, E.stratified_sample(labels, 100, seed=7))
    assert (labels[a] >= 0).all()
    assert (labels[a] == 0).sum() == 90 and (labels[a] == 1).sum() == 10


def test_footprint_and_centroid_matching():
    x, y = np.array([5, 15, 250]), np.array([5, 5, 250])
    fp = E.footprint(x, y, np.array([0, 0, -1]), 100)
    assert fp == {(0, 0)}
    assert E.jaccard({(0, 0), (1, 1)}, {(0, 0)}) == 0.5 and E.jaccard(set(), set()) is None
    m = E.match_centroids(np.array([[0, 0], [1000, 0]]), np.array([[1000, 30], [0, 40]]))
    assert m["matched"] == 2 and m["max_m"] == pytest.approx(40)


def test_structure_diagnostics_detects_chaining_single_locations_and_activity():
    # küme 0: tek konum, 3 olay, 2 yıl; küme 1: 0–300 m zincir, 3 konum, 3 yıl; gürültü yok sayılır
    labels = np.array([0, 0, 0, 1, 1, 1, -1])
    x = np.array([0, 0, 0, 1000, 1150, 1300, 5000.0])
    y = np.zeros(7)
    loc = np.array([7, 7, 7, 1, 2, 3, 9])
    year = np.array([2013, 2013, 2014, 2013, 2014, 2015, 2015])
    d = E.structure_diagnostics(labels, x, y, loc, year, [2013, 2014, 2015], chain_threshold_m=200)
    assert d["n_clusters"] == 2 and d["clustered_events"] == 6
    assert d["single_location_cluster_share"] == 0.5 and d["events_in_single_location_clusters_share"] == 0.5
    assert d["extent_diag_m"]["max"] == pytest.approx(300) and d["clusters_over_threshold_share"] == 0.5
    assert d["active_years"]["share_all_years"] == 0.5 and d["unique_locations_per_cluster"]["max"] == 3
    assert E.structure_diagnostics(np.array([-1, -1]), x[:2], y[:2], loc[:2], year[:2], [2013])["n_clusters"] == 0


# ---------------------------------------------------------------- kayıt ve yapılandırma
def test_experiment_id_is_deterministic():
    a = experiment_id("dbscan", {"eps_m": 50, "min_samples": 10}, "A", {"x": 1}, "v1")
    assert a == experiment_id("dbscan", {"min_samples": 10, "eps_m": 50}, "A", {"x": 1}, "v1")
    assert a != experiment_id("dbscan", {"eps_m": 51, "min_samples": 10}, "A", {"x": 1}, "v1")
    assert a != experiment_id("dbscan", {"eps_m": 50, "min_samples": 10}, "A", {"x": 1}, "v2")


def test_registry_rejects_silent_failures(tmp_path):
    with pytest.raises(ValueError):
        ExperimentRecord("x", "s", "dbscan", {}, "A", {}, "v", "p", status="failed")
    with pytest.raises(ValueError):
        ExperimentRecord("x", "s", "dbscan", {}, "A", {}, "v", "p", status="mystery", error="e")
    reg = Registry(tmp_path / "r.json")
    reg.add(ExperimentRecord("b-1", "s", "dbscan", {}, "A", {}, "v", "p", status="success"))
    reg.add(ExperimentRecord("a-1", "s", "dbscan", {}, "A", {}, "v", "p", status="skipped_resource_limit", error="sınır"))
    assert [r["experiment_id"] for r in Registry(tmp_path / "r.json").ordered()] == ["a-1", "b-1"]


def test_config_validation(tmp_path):
    cfg = load_config()
    assert cfg["dbscan"]["eps_m"] and len(cfg["_sha256"]) == 64
    bad = tmp_path / "bad.toml"
    bad.write_text(open(cfg["_path"], encoding="utf-8").read().replace("eps_m = [25, 50, 100, 200, 350]",
                                                                       "eps_m = [0, 50]"), encoding="utf-8")
    with pytest.raises(ConfigError, match="eps_m"):
        load_config(bad)
    missing = tmp_path / "missing.toml"
    missing.write_text("[meta]\nrandom_seed = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Eksik"):
        load_config(missing)


# ---------------------------------------------------------------- profiller ve GeoJSON
def test_profiles_conserve_counts_and_geojson_is_lon_lat():
    lat = np.array([40.700, 40.7001, 40.7002, 40.700, 40.750, 40.7501, 40.80])
    lon = np.array([-73.990, -73.9901, -73.9899, -73.990, -73.950, -73.9501, -73.90])
    x, y = project(lat, lon)
    labels = np.array([0, 0, 0, 0, 1, 1, -1])
    loc = np.array([0, 1, 2, 0, 3, 4, 5])
    attrs = pd.DataFrame({
        "borough_final": ["MANHATTAN"] * 4 + ["QUEENS"] * 2 + [None],
        "crash_date": pd.to_datetime(["2020-01-01"] * 3 + ["2021-05-05"] + ["2019-01-01"] * 3),
        "crash_hour": pd.array([8, 8, 9, 17, 22, 22, 1], dtype="Int8"),
        "time_period": ["morning"] * 3 + ["afternoon"] + ["evening"] * 2 + ["night"],
        "has_reported_injury": [True, False, False, True, False, False, True],
        "has_reported_fatality": [False] * 6 + [True],
        "number_of_persons_injured": pd.array([1, 0, 0, 2, 0, 0, 1], dtype="Int32"),
        "number_of_persons_killed": pd.array([0] * 6 + [1], dtype="Int32"),
        "vehicle_category_1": ["SUV"] * 3 + ["TAXI_FOR_HIRE"] + ["BUS"] * 2 + [None],
        "contributing_factor_vehicle_1": ["Unspecified", "Driver Inattention/Distraction"] * 3 + [None],
        "on_street_name": ["BROADWAY"] * 4 + ["MAIN ST"] * 2 + [None],
    })
    summary, geo = cluster_profiles(labels, x, y, loc, attrs, "exp-test")
    assert summary["n_events"].sum() == (labels >= 0).sum()                    # üyelik sayısı korunur
    top = summary.iloc[0]
    assert top["cluster_id"] == 0 and top["n_events"] == 4 and top["n_unique_locations"] == 3
    assert top["injury_crashes"] == 2 and top["persons_injured"] == 3 and top["dominant_borough"] == "MANHATTAN"
    assert sum(top["hour_histogram"]) == 4 and top["date_min"] == "2020-01-01" and top["date_max"] == "2021-05-05"
    assert summary.loc[summary["cluster_id"] == 1, "geometry_kind"].item().startswith("buffer")   # 2 nokta: doğrusal
    assert len(geo["features"]) == 2
    for f in geo["features"]:
        ring = f["geometry"]["coordinates"][0]
        lon0, lat0 = ring[0]
        assert -75 < lon0 < -73 and 40 < lat0 < 41                         # RFC 7946: [boylam, enlem]
        row = summary[summary["cluster_id"] == f["properties"]["cluster_id"]].iloc[0]
        assert f["properties"]["n_events"] == row["n_events"]                 # serileştirme doğruluğu
    json.dumps(geo)
