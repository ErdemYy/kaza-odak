"""Faz 5 analitik katmanı: filtre doğruluğu, mevcut-küme / yeniden kümeleme ayrımı, laboratuvar parametre
denetimleri, iş durumları (gerçek ayrı süreç), önbellek, kayıtlı deney yükleme, dışa aktarma ve API hataları."""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from saferoute.analytics.events import EVENT_COLUMNS, FACTOR_COLUMNS, INVOLVES_COLUMNS, EventStore, columns_from_frame
from saferoute.analytics.filters import FilterError, FilterSpec, build_mask, parse_filters
from saferoute.analytics.lab_spec import LabRequestError, validate_request
from saferoute.analytics.reporting import ReportDocument, render
from saferoute.analytics.results import LabelResult
from saferoute.viz.layers import build_layers

from test_viz_layers_api import EXP, make_phase3

N_EVENTS = 60


def make_events(pdir) -> pd.DataFrame:
    """make_phase3'teki 60 olaya (konum ağırlıklarıyla) bilinen öznitelikler atar + 3 uygun olmayan kayıt."""
    locs = pd.read_parquet(pdir / "locations.parquet")
    loc_ids = np.repeat(locs["location_id"].to_numpy(), locs["weight"].to_numpy())
    n = len(loc_ids)
    i = np.arange(n)
    dates = pd.Timestamp("2019-01-01") + pd.to_timedelta((i * 13) % 900, unit="D")
    df = pd.DataFrame({
        "collision_id": i + 1000, "location_id": loc_ids, "eligible_for_spatial_clustering": True,
        "crash_date": dates, "days_since_epoch": ((dates - pd.Timestamp("1970-01-01")).days).astype("int32"),
        "crash_year": dates.year.astype("int16"), "crash_month": dates.month.astype("int8"),
        "day_of_week": dates.dayofweek.astype("int8"), "crash_hour": (i % 24).astype("int8"),
        "borough_final": pd.array(locs["borough"].to_numpy()[loc_ids], dtype="string"),
        "midnight_suspect_flag": (i % 24) == 0, "has_reported_injury": (i % 3) == 0, "has_reported_fatality": i == 7,
        "number_of_persons_injured": ((i % 3) == 0).astype("int32") * 2, "number_of_persons_killed": (i == 7).astype("int32"),
    })
    factors = ["Unspecified", "Driver Inattention/Distraction", "Following Too Closely", None]
    for j, c in enumerate(FACTOR_COLUMNS):
        df[c] = pd.array([factors[(k + j) % 4] if j < 2 else None for k in i], dtype="string")
    for b, c in enumerate(INVOLVES_COLUMNS):
        df[c] = (i % 12) == b
    df.loc[5, "borough_final"] = pd.NA  # ilçesi bilinmeyen uygun olay
    bad = df.iloc[:3].copy()
    bad["eligible_for_spatial_clustering"] = False
    bad["collision_id"] = [1, 2, 3]
    bad["location_id"] = -1
    full = pd.concat([df, bad], ignore_index=True)
    full.to_parquet(pdir / "crashes_processed.parquet", index=False)
    return df


@pytest.fixture()
def world(tmp_path):
    pdir = make_phase3(tmp_path)
    lm = build_layers(pdir, with_boroughs=False, log=lambda _: None)
    events = make_events(pdir)
    store = EventStore.from_processed(pdir, pdir / "phase4", EXP)
    return pdir, lm, events, store


# ----------------------------------------------------------------------------- filtreler
def test_filter_validation_rejects_bad_input():
    with pytest.raises(FilterError, match="ilçe"):
        parse_filters({"boroughs": "PARIS"})
    with pytest.raises(FilterError, match="0–23"):
        parse_filters({"hour_from": "25", "hour_to": "3"})
    with pytest.raises(FilterError, match="birlikte"):
        parse_filters({"hour_from": "4"})
    with pytest.raises(FilterError, match="sonra"):
        parse_filters({"date_from": "2020-02-01", "date_to": "2020-01-01"})
    with pytest.raises(FilterError, match="YYYY"):
        parse_filters({"date_from": "01/02/2020"})
    with pytest.raises(FilterError, match="araç"):
        parse_filters({"vehicles": "SPACESHIP"})
    with pytest.raises(FilterError, match="katkı"):
        parse_filters({"factor": "Yok böyle"}, factors={"Unspecified"})
    spec = parse_filters({"boroughs": "queens,BRONX,queens", "years": "2020,2019", "exclude_midnight": "true"})
    assert spec.boroughs == ("BRONX", "QUEENS") and spec.years == (2019, 2020) and spec.exclude_midnight
    assert parse_filters({"years": "2019,2020"}).key() == parse_filters({"years": "2020,2019"}).key()
    assert FilterSpec().is_empty() and not spec.is_empty()


def test_build_mask_matches_hand_counts():
    hour = np.array([0, 5, 12, 22, 23, 3], dtype=np.int8)
    cols = {"borough": np.array([0, 1, 1, 2, 5, 0], np.int8), "days": np.arange(6, dtype=np.int32) + 18000,
            "year": np.full(6, 2019, np.int16), "month": np.ones(6, np.int8), "dow": np.arange(6, dtype=np.int8),
            "hour": hour, "vehicle_bits": np.array([1, 2, 3, 128, 0, 1], np.uint16),
            "factors": np.array([[0, -1, -1, -1, -1], [1, 0, -1, -1, -1]] * 3, np.int16),
            "injury": np.array([1, 0, 1, 0, 1, 0], bool), "fatal": np.array([0, 0, 0, 0, 1, 0], bool),
            "midnight": hour == 0}
    m = lambda **kw: build_mask(cols, FilterSpec(**kw)).nonzero()[0].tolist()  # noqa: E731
    assert m(boroughs=("BROOKLYN",)) == [1, 2]
    assert m(hour_from=22, hour_to=3) == [0, 3, 4, 5]          # gece yarısını aşan aralık
    assert m(hour_from=5, hour_to=12) == [1, 2]
    assert m(vehicles=("SUV",)) == [1, 2]                       # bit 1
    assert m(vehicles=("PASSENGER_CAR", "BICYCLE")) == [0, 2, 3, 5]
    assert m(injury="injury", fatal="non_fatal") == [0, 2]
    assert m(exclude_midnight=True) == [1, 2, 3, 4, 5]
    d0 = pd.Timestamp("1970-01-01") + pd.Timedelta(days=18000)
    assert m(date_from=d0.date().isoformat(), date_to=d0.date().isoformat()) == [0]
    assert build_mask(cols, FilterSpec(factor="x"), factor_code=1).nonzero()[0].tolist() == [1, 3, 5]
    assert not build_mask(cols, FilterSpec(factor="x"), factor_code=None).any()


# ----------------------------------------------------------------------------- olay deposu
def test_store_counts_and_mode_separation(world):
    pdir, lm, ev, store = world
    assert store.n_events == N_EVENTS and store.n_clusters == lm["counts"]["clusters"]
    full = store.summary(FilterSpec())
    assert full["n_events"] == N_EVENTS
    assert full["model"]["events_in_clusters"] == lm["counts"]["events_clustered"]
    assert full["injury_crashes"] == int((np.arange(N_EVENTS) % 3 == 0).sum())
    assert full["fatal_crashes"] == 1 and full["persons_killed"] == 1
    assert sum(r["events"] for r in full["by_borough"]) == N_EVENTS
    assert next(r for r in full["by_borough"] if r["borough"] == "UNKNOWN")["events"] == 1
    # Filtre: Manhattan — etiketler TAM VERİ modelinden gelir (yeniden kümeleme yok)
    spec = parse_filters({"boroughs": "MANHATTAN"})
    s = store.summary(spec)
    exp_n = int(((ev["borough_final"] == "MANHATTAN").fillna(False)).sum())
    assert s["n_events"] == exp_n
    assert s["model"]["label_source"].startswith("tam veri") and s["model"]["clusters_total"] == 3
    counts = store.cluster_counts(spec)
    layer = pd.read_parquet(pdir / "phase4" / "locations_layer.parquet").set_index("location_id")["cluster_id"]
    lab = layer.reindex(ev["location_id"]).to_numpy()
    sel = (ev["borough_final"] == "MANHATTAN").fillna(False).to_numpy()
    for cid in range(3):
        assert counts[cid] == int(((lab == cid) & sel).sum())


def test_density_points_and_timeline_sums(world):
    _, _, ev, store = world
    spec = parse_filters({"years": "2019"})
    n = int((ev["crash_year"] == 2019).sum())
    for cell in store.cell_index:
        d = store.density(spec, cell)
        assert d["total_events"] == n == sum(f["properties"]["events"] for f in d["features"])
        assert all(f["properties"]["clustered"] + f["properties"]["noise"] == f["properties"]["events"] for f in d["features"])
    p = store.points(spec, (-75, 40, -73, 41), "all", 1000)
    assert p["total_events"] == n and not p["truncated"]
    p2 = store.points(spec, (-75, 40, -73, 41), "all", 2)
    assert p2["truncated"] and p2["returned_locations"] == 2 and p2["total_events"] == n
    clustered = store.points(spec, (-75, 40, -73, 41), "clustered", 1000)
    assert all(not f["properties"]["noise"] for f in clustered["features"])
    tl = store.timeline(FilterSpec(), "month")
    assert sum(b["count"] for b in tl["buckets"]) == N_EVENTS
    assert sum(b["count"] for b in store.timeline(FilterSpec(), "hour")["buckets"]) == N_EVENTS


def test_factor_counts_once_per_crash_and_excludes_unspecified(world):
    _, _, ev, store = world
    s = store.summary(FilterSpec())
    names = [f["value"] for f in s["top_factors"]]
    assert "Unspecified" not in names
    expect = int(((ev[FACTOR_COLUMNS[0]] == "Driver Inattention/Distraction") |
                  (ev[FACTOR_COLUMNS[1]] == "Driver Inattention/Distraction")).fillna(False).sum())
    assert next(f for f in s["top_factors"] if f["value"] == "Driver Inattention/Distraction")["crashes"] == expect
    f1 = ev[FACTOR_COLUMNS[0]]
    assert s["factor_unspecified_share"] == pytest.approx(float((f1 == "Unspecified").sum() / f1.notna().sum()))


def test_columns_from_frame_handles_plain_strings():
    df = pd.DataFrame({c: [] for c in EVENT_COLUMNS})
    cols = columns_from_frame(df.astype({"eligible_for_spatial_clustering": bool}))
    assert len(cols.days) == 0 and cols.factors.shape == (0, 5)


# ----------------------------------------------------------------------------- laboratuvar istekleri
@pytest.mark.parametrize("body,match", [
    ({"algorithm": "kmeans", "feature_set": "spatiotemporal", "params": {"k": 5}}, "desteklenmiyor"),
    ({"algorithm": "kmeans", "feature_set": "spatial_haversine", "params": {"k": 5}}, "desteklenmiyor"),
    ({"algorithm": "hdbscan", "feature_set": "spatial_haversine", "params": {"min_cluster_size": 5}}, "desteklenmiyor"),
    ({"algorithm": "dbscan", "feature_set": "spatial_projected", "params": {"eps_m": 25, "min_samples": 5}}, "desteklenmiyor"),
    ({"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 0, "min_samples": 5}}, "eps_m"),
    ({"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 25, "min_samples": 1.5}}, "tamsayı"),
    ({"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 25, "min_samples": 5, "eps_days": 3}}, "eps_days"),
    ({"algorithm": "dbscan", "feature_set": "spatiotemporal", "params": {"eps_m": 25, "min_samples": 5}}, "eps_days"),
    ({"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 1}}, "k 2"),
    ({"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 5, "n_init": 50}}, "n_init"),
    ({"algorithm": "hdbscan", "feature_set": "spatial_projected", "params": {"min_cluster_size": 1}}, "min_cluster_size"),
    ({"algorithm": "hdbscan", "feature_set": "spatial_projected", "params": {"min_cluster_size": 5, "alpha": 2}}, "tanımsız"),
    ({"algorithm": "optics", "feature_set": "spatial_projected", "params": {}}, "algorithm"),
    ({"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 25, "min_samples": 5},
      "filters": {"boroughs": "PARIS"}}, "ilçe"),
])
def test_lab_request_validation(body, match):
    with pytest.raises(LabRequestError, match=match):
        validate_request(body)


def test_lab_request_defaults_and_cache_key():
    a = validate_request({"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 5}})
    assert a.params == {"k": 5, "n_init": 10, "max_iter": 300, "random_state": 42}
    b = validate_request({"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 5, "random_state": 1}})
    assert a.cache_key("dv") != b.cache_key("dv") and a.cache_key("dv") != a.cache_key("dv2")
    h = validate_request({"algorithm": "hdbscan", "feature_set": "spatial_haversine_records",
                          "params": {"min_cluster_size": 5}, "sample": {"n": 5000}})
    assert h.params["min_samples"] is None and h.sample == {"n": 5000, "seed": 42}


# ----------------------------------------------------------------------------- sonuç özeti
def test_label_result_summary_and_kmeans_noise_na(world):
    _, _, ev, store = world
    idx = np.arange(N_EVENTS)
    lab = np.where(np.arange(N_EVENTS) < 20, 0, np.where(np.arange(N_EVENTS) < 50, 1, -1)).astype(np.int32)
    r = LabelResult(store, idx, lab, "dbscan", "t")
    s = r.summary()
    assert s["n_clusters"] == 2 and s["noise_events"] == 10 and s["noise_ratio"] == pytest.approx(10 / 60)
    assert sum(row["n_events"] for row in r.export_rows()) == 50
    assert r.centroids()["returned"] == 2
    km = LabelResult(store, idx, np.where(lab < 0, 1, lab).astype(np.int32), "kmeans", "k").summary()
    assert km["noise_ratio"] is None and km["noise_events"] is None and not km["noise_applicable"]
    d = r.cluster_detail(1)
    assert d["n_events"] == 30 and sum(d["hour_histogram"]) == 30
    assert r.cluster_detail(99) is None


def test_report_formats():
    doc = ReportDocument(kind="t", title="Deneme", source={"dataset_id": "x"}, data_version="dv",
                         algorithm={"name": "DBSCAN", "parameters": {"eps_m": 25}}, filters=["İlçe: BRONX"], n_records=1234,
                         metrics={"siluet": 0.5}, table=[{"küme": 1, "olay": 10}])
    md, mime, ext = render(doc, "md")
    assert "Sınırlılıklar" in md and "1.234" in md and "DBSCAN" in md and ext == "md"
    csv_body, _, _ = render(doc, "csv")
    assert csv_body.startswith("﻿küme,olay")
    js = json.loads(render(doc, "json")[0])
    assert js["schema"] == "saferoute.report/1" and js["limitations"]
    with pytest.raises(ValueError):
        render(doc, "pdf")


# ----------------------------------------------------------------------------- API (gerçek ayrı süreçli işler)
def write_catalog(pdir, store):
    """Faz 3 kayıt dosyalarının küçük bir örneği: seçili DBSCAN ızgara deneyi ve etiketleri."""
    p3 = pdir / "phase3"
    (p3 / "labels").mkdir(exist_ok=True)
    layer = pd.read_parquet(pdir / "phase4" / "locations_layer.parquet").set_index("location_id")["cluster_id"]
    labels = layer.reindex(store.c.location).to_numpy().astype(np.int32)
    np.savez_compressed(p3 / "labels" / f"{EXP}.npz", event_index=np.arange(store.n_events), labels=labels)
    reg = [{"experiment_id": EXP, "stage": "dbscan_grid", "algorithm": "dbscan", "params": {"eps_m": 25, "min_samples": 5},
            "feature_set": "A_dbscan_haversine_weighted", "scope": {"kind": "dbscan_weighted", "subset": None},
            "dataset_version": "dv", "status": "success", "n_events": store.n_events, "n_unique_locations": 12,
            "runtime_s": 0.1, "peak_memory_mb": 100.0, "labels_path": str(p3 / "labels" / f"{EXP}.npz")}]
    (p3 / "experiments.json").write_text(json.dumps(reg), encoding="utf-8")
    (p3 / "results.json").write_text(json.dumps({"evaluation": {"table": []}, "dbscan_grid_ids": [EXP]}), encoding="utf-8")


@pytest.fixture()
def api(world):
    from fastapi.testclient import TestClient

    from saferoute.viz.api import create_app

    pdir, lm, ev, store = world
    write_catalog(pdir, store)
    app = create_app(pdir / "phase4", analytics={"lab_root": pdir / "lab"})
    c = TestClient(app)
    deadline = time.time() + 30
    while not c.get("/api/analytics/status").json()["ready"]:
        assert time.time() < deadline
        time.sleep(0.05)
    yield c, pdir, ev
    app.state.analytics.jobs.shutdown()


def wait_job(c, jid, timeout=120):
    states = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = c.get(f"/api/lab/jobs/{jid}").json()
        if not states or states[-1] != j["state"]:
            states.append(j["state"])
        if j["state"] in ("completed", "failed", "cancelled", "resource_limited"):
            return j, states
        time.sleep(0.1)
    raise AssertionError(f"iş bitmedi: {states}")


def test_api_records_and_validation(api):
    c, _, ev = api
    assert c.get("/api/records/summary").json()["n_events"] == N_EVENTS
    assert c.get("/api/records/summary?boroughs=PARIS").status_code == 422
    assert c.get("/api/records/summary?hour_from=3").status_code == 422
    r = c.get("/api/records/clusters?boroughs=MANHATTAN").json()
    assert r["label_source"].startswith("tam veri")
    assert all(f["properties"]["n_events"] <= f["properties"]["n_events_full"] for f in r["features"])
    d = c.get("/api/records/clusters/0?boroughs=MANHATTAN").json()
    assert d["filters_active"] and d["full"]["cluster_id"] == 0 and d["filtered"]["n_events"] <= d["full"]["n_events"]
    assert c.get(f"/api/records/clusters/0?experiment_id=baska").status_code == 409
    assert c.get("/api/records/clusters/999").status_code == 404
    assert c.get("/api/records/density?cell=333").status_code == 422
    assert c.get("/api/records/points?bbox=-75,40,-73,41").status_code == 413  # Faz 4 kutu sınırı korunur
    assert c.get("/api/records/points?bbox=-73.99,40.75,-73.97,40.77").json()["total_events"] >= 0
    opt = c.get("/api/filters/options").json()
    assert opt["n_events"] == N_EVENTS and {b["value"] for b in opt["boroughs"]} >= {"MANHATTAN"}
    csv_text = c.get("/api/export/records?boroughs=MANHATTAN&format=csv").text
    assert csv_text.startswith("﻿cluster_id")
    assert "YENİDEN KÜMELEME YAPILMADI" in c.get("/api/export/records?format=md").text
    assert c.get("/api/export/records?format=pdf").status_code == 422


def test_api_saved_experiment_and_registry_reuse(api):
    c, _, _ = api
    ex = c.get("/api/experiments").json()
    assert ex["count"] == 1 and ex["experiments"][0]["has_labels"]
    s = c.get(f"/api/results/{EXP}/summary").json()["summary"]
    assert s["n_clusters"] == 3 and s["n_events"] == N_EVENTS
    assert c.get("/api/results/yok-boyle/summary").status_code == 404
    # Aynı konfigürasyon + filtresiz istek → kayıtlı Faz 3 sonucu, yeniden fit yok
    j = c.post("/api/lab/jobs", json={"algorithm": "dbscan", "feature_set": "spatial_haversine",
                                      "params": {"eps_m": 25, "min_samples": 5}}).json()
    assert j["state"] == "completed" and j["source"] == "phase3_registry" and j["phase3_experiment"] == EXP
    # Filtreli aynı konfigürasyon kayıtlı sonuç DEĞİLDİR → yeni iş
    j2 = c.post("/api/lab/jobs", json={"algorithm": "dbscan", "feature_set": "spatial_haversine",
                                       "params": {"eps_m": 25, "min_samples": 5}, "filters": {"boroughs": "MANHATTAN"}}).json()
    assert j2["source"] == "dynamic" and j2["state"] in ("queued", "running")
    c.delete(f"/api/lab/jobs/{j2['job_id']}")


def test_api_dynamic_job_lifecycle_cache_and_export(api):
    c, _, _ = api
    body = {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 40, "min_samples": 6}}
    j = c.post("/api/lab/jobs", json=body)
    assert j.status_code == 202
    job, states = wait_job(c, j.json()["job_id"])
    assert job["state"] == "completed", job["error"]
    assert states[-1] == "completed"
    assert job["worker"]["runtime_s"] >= 0 and job["worker"]["peak_memory_mb"] > 0
    assert job["result"]["summary"]["n_events"] == N_EVENTS
    rid = f"lab-{job['job_id']}"
    assert c.get(f"/api/results/{rid}/clusters").json()["total_clusters"] == job["result"]["summary"]["n_clusters"]
    assert c.get(f"/api/results/{rid}/table?limit=1").json()["limit"] == 1
    again = c.post("/api/lab/jobs", json=body).json()
    assert again["state"] == "completed" and again["source"] == "cache"
    md = c.get(f"/api/export/results/{rid}?format=md").text
    assert "eps_m" in md and "Sınırlılıklar" in md


def test_api_kmeans_and_hdbscan_jobs(api):
    c, _, _ = api
    km = c.post("/api/lab/jobs", json={"algorithm": "kmeans", "feature_set": "spatial_projected",
                                       "params": {"k": 3, "n_init": 2, "random_state": 0}}).json()
    job, _ = wait_job(c, km["job_id"])
    assert job["state"] == "completed", job["error"]
    assert job["result"]["summary"]["noise_ratio"] is None and job["result"]["summary"]["n_clusters"] == 3
    hd = c.post("/api/lab/jobs", json={"algorithm": "hdbscan", "feature_set": "spatial_projected",
                                       "params": {"min_cluster_size": 5}}).json()
    job, _ = wait_job(c, hd["job_id"])
    assert job["state"] == "completed", job["error"]


def test_api_resource_rejection_and_empty_scope(api):
    c, pdir, _ = api
    jm = c.app.state.analytics.jobs
    jm.budget["max_hdbscan_events"] = 10
    r = c.post("/api/lab/jobs", json={"algorithm": "hdbscan", "feature_set": "spatial_projected",
                                      "params": {"min_cluster_size": 5}}).json()
    assert r["state"] == "resource_limited" and "örneklem" in r["error"]
    jm.budget["max_neighbor_pairs"] = 1
    r = c.post("/api/lab/jobs", json={"algorithm": "dbscan", "feature_set": "spatial_haversine",
                                      "params": {"eps_m": 41, "min_samples": 6}}).json()
    job, _ = wait_job(c, r["job_id"])
    assert job["state"] == "resource_limited" and "komşu çifti" in job["error"]
    e = c.post("/api/lab/jobs", json={"algorithm": "dbscan", "feature_set": "spatial_haversine",
                                      "params": {"eps_m": 25, "min_samples": 5}, "filters": {"years": "1999"}})
    assert e.status_code == 422 and "kayıt yok" in e.json()["detail"]
    assert c.post("/api/lab/jobs", json={"algorithm": "kmeans", "feature_set": "spatiotemporal", "params": {"k": 3}}).status_code == 422
    assert c.get("/api/lab/jobs/yok").status_code == 404
    assert c.get("/api/results/lab-yok/summary").status_code == 404


def test_api_cancel_pending_job(api):
    c, _, _ = api
    jm = c.app.state.analytics.jobs
    bodies = [{"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 30 + i, "min_samples": 5}}
              for i in range(3)]
    ids = [c.post("/api/lab/jobs", json=b).json()["job_id"] for b in bodies]
    last = c.delete(f"/api/lab/jobs/{ids[-1]}").json()
    assert last["state"] in ("cancelled", "running")
    for jid in ids:
        wait_job(c, jid)
    assert c.get(f"/api/lab/jobs/{ids[-1]}").json()["state"] in ("cancelled", "completed")
    assert c.get(f"/api/results/lab-{ids[-1]}/summary").status_code in (200, 409)
    assert jm.max_pending == 3


def test_analytics_disabled_without_processed_data(tmp_path):
    from fastapi.testclient import TestClient

    from saferoute.viz.api import create_app

    pdir = make_phase3(tmp_path)
    build_layers(pdir, with_boroughs=False, log=lambda _: None)
    c = TestClient(create_app(pdir / "phase4"))
    st = c.get("/api/analytics/status").json()
    assert not st["ready"] and "devre dışı" in st["error"]
    assert c.get("/api/records/summary").status_code == 503
    assert c.get("/api/meta").status_code == 200  # Faz 4 uç noktaları etkilenmez


def test_real_store_matches_phase4_layer():
    """Gerçek veri varsa: filtresiz kayıt sayıları Faz 4 katman manifestiyle aynı olmalı."""
    from saferoute.clustering.data import processed_dir

    try:
        pdir = processed_dir()
    except Exception:
        pytest.skip("gerçek veri yok")
    if not (pdir / "phase4" / "layer_manifest.json").exists():
        pytest.skip("Faz 4 katmanları yok")
    lm = json.loads((pdir / "phase4" / "layer_manifest.json").read_text(encoding="utf-8"))
    store = EventStore.from_processed(pdir, pdir / "phase4", lm["model"]["experiment_id"])
    s = store.summary(FilterSpec())
    assert s["n_events"] == lm["counts"]["events_total"]
    assert s["model"]["events_in_clusters"] == lm["counts"]["events_clustered"]
    assert store.density(FilterSpec(), 1000)["total_events"] == lm["counts"]["events_total"]
