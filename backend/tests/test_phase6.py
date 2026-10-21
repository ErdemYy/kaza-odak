"""Faz 6: kalıcı iş kaydı, yeniden başlatma uzlaştırması, iptal ve süreç doğrulaması, kaynak sınırlama,
dinamik/kayıtlı deney kimliği, filtre/yeniden kümeleme ayrımı, zaman oynatma doğruluğu, sayfalama,
GeoJSON geçerliliği ve API güvenlik sınırları. İşler GERÇEK ayrı süreçlerde çalışır."""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time

import numpy as np
import psutil
import pytest

from saferoute.analytics.jobstore import JobStore

from test_analytics import N_EVENTS, wait_job as _wait_job, world, write_catalog  # noqa: F401  (fikstür)
from test_viz_layers_api import EXP

TERMINAL = ("completed", "failed", "cancelled", "interrupted", "resource_limited")
DBSCAN = {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 40, "min_samples": 6}}


def wait_job(c, jid, timeout=120):
    deadline = time.time() + timeout
    states = []
    while time.time() < deadline:
        j = c.get(f"/api/lab/jobs/{jid}").json()
        if not states or states[-1] != j["state"]:
            states.append(j["state"])
        if j["state"] in TERMINAL:
            return j, states
        time.sleep(0.1)
    raise AssertionError(f"iş bitmedi: {states}")


def make_client(pdir, budget=None):
    from fastapi.testclient import TestClient

    from saferoute.viz.api import create_app

    opts = {"lab_root": pdir / "lab"}
    if budget:
        opts["budget"] = budget
    app = create_app(pdir / "phase4", analytics=opts)
    c = TestClient(app)
    deadline = time.time() + 30
    while not c.get("/api/analytics/status").json()["ready"]:
        assert time.time() < deadline
        time.sleep(0.05)
    return c


@pytest.fixture()
def pdir(world):  # noqa: F811
    p, _, _, store = world
    write_catalog(p, store)
    return p


@pytest.fixture()
def client(pdir):
    c = make_client(pdir)
    yield c
    c.app.state.analytics.jobs.shutdown()


def _sleeper(seconds: float) -> None:  # yetim süreç benzetimi (multiprocessing komut satırıyla)
    time.sleep(seconds)


# ----------------------------------------------------------------------------- kalıcı kayıt
def test_jobstore_atomic_cas_and_schema(tmp_path):
    db = JobStore(tmp_path / "jobs.sqlite3")
    rec = {"job_id": "a" * 12, "experiment_id": "dyn-x", "cache_key": "k", "algorithm": "dbscan",
           "feature_set": "spatial_haversine", "params": {"eps_m": 5}, "request": {"algorithm": "dbscan"},
           "state": "queued", "submitted_at": time.time()}
    db.insert(rec)
    assert db.update("a" * 12, {"state": "running"}, expect=("queued",))
    assert not db.update("a" * 12, {"state": "completed"}, expect=("queued",))   # yarış: eski durum beklenirse yazmaz
    assert db.update("a" * 12, {"state": "cancelled"}, expect=("running",))
    assert not db.update("a" * 12, {"state": "completed"}, expect=("running",))  # iptal edilen iş başarılı olamaz
    assert db.get("a" * 12)["state"] == "cancelled" and db.get("a" * 12)["params"] == {"eps_m": 5}
    with pytest.raises(ValueError):
        db.update("a" * 12, {"state": "bitti"})
    with pytest.raises(KeyError):
        db.update("a" * 12, {"bilinmeyen": 1})
    assert db.integrity() == "ok"
    db.close()
    assert JobStore(tmp_path / "jobs.sqlite3").get("a" * 12)["state"] == "cancelled"  # yeniden açınca kalıcı


def test_completed_job_and_result_survive_restart(pdir):
    c = make_client(pdir)
    j = c.post("/api/lab/jobs", json=DBSCAN).json()
    job, _ = wait_job(c, j["job_id"])
    assert job["state"] == "completed", job["error"]
    assert job["experiment_id"] == f"dyn-{job['cache_key']}" and job["output_sha256"]
    summary = c.get(f"/api/results/lab-{job['job_id']}/summary").json()["summary"]
    c.app.state.analytics.jobs.shutdown()
    c.app.state.analytics.jobs.db.close()

    c2 = make_client(pdir)  # "sunucu yeniden başladı": yeni süreç durumu, aynı kalıcı kayıt
    try:
        again = c2.get(f"/api/lab/jobs/{job['job_id']}").json()
        assert again["state"] == "completed" and again["result"]["summary"] == job["result"]["summary"]
        assert c2.get(f"/api/results/lab-{job['job_id']}/summary").json()["summary"] == summary
        assert c2.get(f"/api/results/{job['experiment_id']}/summary").json()["summary"] == summary
        assert any(r["job_id"] == job["job_id"] for r in c2.get("/api/lab/jobs").json()["jobs"])
        rec = c2.get("/api/analytics/status").json()["job_recovery"]
        assert rec["checked"] == 0 and rec["db_integrity"] == "ok"
    finally:
        c2.app.state.analytics.jobs.shutdown()


def test_stale_jobs_reconciled_without_rerun_and_orphan_killed(pdir):
    c = make_client(pdir)
    jm = c.app.state.analytics.jobs
    done = c.post("/api/lab/jobs", json=DBSCAN).json()
    done, _ = wait_job(c, done["job_id"])
    jm.shutdown()
    db = jm.db
    now = time.time()
    # Gerçek bir yetim çalışan benzetimi: spawn çocuğu (komut satırında 'multiprocessing')
    orphan = mp.get_context("spawn").Process(target=_sleeper, args=(60,))
    orphan.start()
    ct = psutil.Process(orphan.pid).create_time()
    base = {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 33, "min_samples": 5},
            "request": {**DBSCAN, "params": {"eps_m": 33, "min_samples": 5}, "filters": {}, "sample": None},
            "submitted_at": now, "experiment_id": "dyn-x"}
    db.insert({**base, "job_id": "1" * 12, "cache_key": "a" * 16, "state": "running", "started_at": now,
               "worker_pid": orphan.pid, "worker_create_time": ct})
    db.insert({**base, "job_id": "2" * 12, "cache_key": "b" * 16, "state": "queued"})
    # Çalışırken kapanan ama sonucu (SHA-256'lı) diske yazmış iş: kurtarılır
    db.insert({**base, "job_id": "3" * 12, "cache_key": done["cache_key"], "state": "running", "started_at": now})
    # PID yeniden kullanımı: kayıttaki oluşturulma zamanı tutmuyor → başka sürece DOKUNULMAZ
    me = psutil.Process()
    db.insert({**base, "job_id": "4" * 12, "cache_key": "c" * 16, "state": "running", "started_at": now,
               "worker_pid": me.pid, "worker_create_time": me.create_time() - 1000})
    db.close()

    c2 = make_client(pdir)
    try:
        rep = c2.get("/api/analytics/status").json()["job_recovery"]
        assert sorted(rep["interrupted"]) == ["1" * 12, "2" * 12, "4" * 12]
        assert rep["recovered_completed"] == ["3" * 12]
        assert [o["pid"] for o in rep["orphans_killed"]] == [orphan.pid] and rep["orphans_killed"][0]["verified"]
        orphan.join(5)
        assert not orphan.is_alive()
        assert me.is_running()
        j1 = c2.get(f"/api/lab/jobs/{'1' * 12}").json()
        assert j1["state"] == "interrupted" and j1["retryable"] and "uydurulmadı" in j1["error"]
        assert c2.get(f"/api/lab/jobs/{'2' * 12}").json()["state"] == "interrupted"
        j3 = c2.get(f"/api/lab/jobs/{'3' * 12}").json()
        assert j3["state"] == "completed" and j3["recovered"]
        assert c2.get(f"/api/results/lab-{'3' * 12}/summary").status_code == 200
        # Kontrolsüz yeniden çalıştırma yok: bir süre sonra hâlâ interrupted ve çalışan iş yok
        time.sleep(1.5)
        assert c2.get(f"/api/lab/jobs/{'2' * 12}").json()["state"] == "interrupted"
        assert c2.get("/api/lab/resources").json()["running"] == 0
        # Güvenli yeniden deneme: AÇIK istekle YENİ iş
        r = c2.post(f"/api/lab/jobs/{'1' * 12}/retry")
        assert r.status_code == 202
        new = r.json()
        assert new["job_id"] != "1" * 12 and new["retry_of"] == "1" * 12
        new, _ = wait_job(c2, new["job_id"])
        assert new["state"] == "completed", new["error"]
        assert c2.post(f"/api/lab/jobs/{new['job_id']}/retry").status_code == 409  # tamamlanan iş yeniden denenmez
    finally:
        if orphan.is_alive():
            orphan.kill()
        c2.app.state.analytics.jobs.shutdown()


def test_cancel_running_job_terminates_worker(pdir, monkeypatch):
    monkeypatch.setenv("SAFEROUTE_LAB_TEST_DELAY_S", "30")
    c = make_client(pdir)
    try:
        j = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 44, "min_samples": 6}}).json()
        jm = c.app.state.analytics.jobs
        deadline = time.time() + 60
        pid = None
        while time.time() < deadline:
            rec = jm.db.get(j["job_id"])
            if rec["state"] == "running" and rec["worker_pid"]:
                pid = rec["worker_pid"]
                break
            time.sleep(0.05)
        assert pid and psutil.pid_exists(pid)
        r = c.delete(f"/api/lab/jobs/{j['job_id']}").json()
        assert r["state"] == "cancelled" and "doğrulandı" in r["error"]
        assert r["worker"]["termination"]["verified"]
        assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        time.sleep(1.0)  # izleme döngüsü durumu geri ÇEVİREMEZ (karşılaştır-ve-değiştir)
        assert c.get(f"/api/lab/jobs/{j['job_id']}").json()["state"] == "cancelled"
        assert c.get(f"/api/results/lab-{j['job_id']}/summary").status_code == 409
    finally:
        c.app.state.analytics.jobs.shutdown()


def test_shutdown_marks_running_job_interrupted(pdir, monkeypatch):
    monkeypatch.setenv("SAFEROUTE_LAB_TEST_DELAY_S", "30")
    c = make_client(pdir)
    jm = c.app.state.analytics.jobs
    j = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 45, "min_samples": 6}}).json()
    deadline = time.time() + 60
    while jm.db.get(j["job_id"])["worker_pid"] is None and time.time() < deadline:
        time.sleep(0.05)
    pid = jm.db.get(j["job_id"])["worker_pid"]
    jm.shutdown()
    rec = jm.db.get(j["job_id"])
    assert rec["state"] == "interrupted" and rec["error_kind"] == "interrupted_shutdown"
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_resource_limits(pdir):
    c = make_client(pdir)
    jm = c.app.state.analytics.jobs
    try:
        res = c.get("/api/lab/resources").json()
        assert res["available_memory_mb"] is None or res["available_memory_mb"] > 0
        assert res["max_concurrent"] == 1 and res["worker_memory_limit_mb"] >= jm.budget["min_worker_memory_mb"]
        # Başlatmadan önce ölçülen boş bellek yetersiz → iş çalıştırılmaz, açık mesaj
        jm.memory_probe = lambda: 200.0
        r = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 46, "min_samples": 6}}).json()
        assert r["state"] == "resource_limited" and r["error_kind"] == "resource_memory" and "Bellek yetersiz" in r["error"]
        assert jm.db.get(r["job_id"])["worker_pid"] is None
        assert c.get("/api/lab/resources").json()["can_start"] is False
        jm.memory_probe = lambda: None
        # Kuyruk sınırı (429)
        jm.max_pending = 0
        assert c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 47, "min_samples": 6}}).status_code == 429
    finally:
        jm.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows iş nesnesi bellek tavanı")
def test_worker_memory_cap_enforced_by_job_object(pdir):
    # Tavan, bilimsel kütüphanelerin içe aktarılmasına bile yetmeyecek kadar düşük: iş GÜVENLE sınırlanmalı,
    # sistem belleği tüketilmemeli ve iş başarılı işaretlenmemeli.
    c = make_client(pdir, budget={"max_worker_memory_mb": 120, "min_worker_memory_mb": 120, "min_free_memory_mb": 0})
    try:
        r = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 48, "min_samples": 6}}).json()
        job, _ = wait_job(c, r["job_id"])
        assert job["state"] in ("resource_limited", "failed") and job["state"] != "completed"
        mon = job["worker"]["monitor"]
        assert mon["guard"]["job_object"] and mon["guard"]["memory_limit_mb"] == 120
        assert mon["peak_commit_mb"] is None or mon["peak_commit_mb"] <= 121
    finally:
        c.app.state.analytics.jobs.shutdown()


def test_duplicate_active_request_not_run_twice(pdir, monkeypatch):
    monkeypatch.setenv("SAFEROUTE_LAB_TEST_DELAY_S", "3")
    c = make_client(pdir)
    try:
        body = {**DBSCAN, "params": {"eps_m": 49, "min_samples": 6}}
        a = c.post("/api/lab/jobs", json=body).json()
        b = c.post("/api/lab/jobs", json=body).json()
        assert a["job_id"] == b["job_id"]  # aynı istek kuyrukta/çalışıyorken ikinci kopya açılmaz
        job, _ = wait_job(c, a["job_id"])
        assert job["state"] == "completed"
        cached = c.post("/api/lab/jobs", json=body).json()
        assert cached["source"] == "cache" and cached["result"]["summary"] == job["result"]["summary"]
    finally:
        c.app.state.analytics.jobs.shutdown()


# ----------------------------------------------------------------------------- kimlik ve mod ayrımı
def test_dynamic_vs_saved_identity_and_filter_recluster_separation(client):
    c = client
    saved = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 25, "min_samples": 5}}).json()
    assert saved["source"] == "phase3_registry" and saved["experiment_id"] == EXP
    flt = {"boroughs": "MANHATTAN"}
    dyn = c.post("/api/lab/jobs", json={**DBSCAN, "params": {"eps_m": 25, "min_samples": 5}, "filters": flt}).json()
    dyn, _ = wait_job(c, dyn["job_id"])
    assert dyn["state"] == "completed" and dyn["experiment_id"].startswith("dyn-") and dyn["experiment_id"] != EXP
    # Mod A (filtreleme) ve Mod B (yeni kümeleme) aynı kayıt kapsamı → aynı kayıt sayısı, farklı etiket kaynağı
    records = c.get("/api/records/summary?boroughs=MANHATTAN").json()
    assert dyn["n_events"] == records["n_events"] == dyn["result"]["summary"]["n_events"]
    a = c.get("/api/records/clusters?boroughs=MANHATTAN").json()
    b = c.get(f"/api/results/{dyn['experiment_id']}/clusters").json()
    assert a["experiment_id"] == EXP and a["label_source"].startswith("tam veri")
    assert {f["properties"]["experiment_id"] for f in b["features"]} == {f"lab-{dyn['job_id']}"}
    assert sum(f["properties"]["n_events"] for f in a["features"]) == a["events_in_clusters"]
    assert sum(f["properties"]["n_events"] for f in b["features"]) == dyn["result"]["summary"]["clustered_events"]
    # Sonuç uç noktası kayıt filtresini KABUL ETMEZ (iki mod birleşmez)
    r = c.get(f"/api/results/{EXP}/clusters?boroughs=MANHATTAN")
    assert r.status_code == 422 and "birleştirilmez" in r.json()["detail"]
    # Farklı deneyin küme numarası Faz 4 modeli adına sorgulanamaz
    assert c.get(f"/api/records/clusters/0?experiment_id={dyn['experiment_id']}").status_code == 409


# ----------------------------------------------------------------------------- zaman oynatma
@pytest.mark.parametrize("granularity", ["year", "month", "dow", "hour"])
def test_time_playback_keeps_membership(client, granularity):
    c = client
    full = c.get(f"/api/results/{EXP}/clusters").json()
    pos = {f["properties"]["cluster_id"]: f["geometry"]["coordinates"] for f in full["features"]}
    tl = c.get(f"/api/results/{EXP}/timeline?granularity={granularity}").json()
    assert tl["reclustered"] is False and tl["n_events"] == N_EVENTS == tl["coverage"]["n_events"]
    assert sum(b["count"] for b in tl["buckets"]) == N_EVENTS
    assert tl["coverage"]["date_min"] <= tl["coverage"]["date_max"]
    key = {"year": "years", "month": None, "dow": "dows", "hour": None}[granularity]
    total_visible = 0
    for b in tl["buckets"]:
        if granularity == "month":
            y, m = b["key"].split("-")
            q = f"years={y}&months={int(m)}"
        elif granularity == "hour":
            q = f"hour_from={int(b['key'])}&hour_to={int(b['key'])}"
        else:
            q = f"{key}={b['key']}"
        s = c.get(f"/api/results/{EXP}/clusters?{q}").json()
        assert s["time_slice"]["visible_events"] == b["count"]
        total_visible += s["time_slice"]["visible_events"]
        for f in s["features"]:
            cid = f["properties"]["cluster_id"]
            assert f["geometry"]["coordinates"] == pos[cid]                 # merkez ve üyelik DEĞİŞMEZ
            assert 0 < f["properties"]["n_events"] <= f["properties"]["n_events_full"]
        d = c.get(f"/api/results/{EXP}/density?cell=1000&{q}").json()
        assert d["total_events"] == b["count"]
    assert total_visible == N_EVENTS
    assert c.get(f"/api/results/{EXP}/density?cell=1000").json()["total_events"] == N_EVENTS


# ----------------------------------------------------------------------------- coğrafi veri
def _valid_fc(fc):
    assert fc["type"] == "FeatureCollection"
    for f in fc["features"]:
        assert f["type"] == "Feature" and f["geometry"]["type"] in ("Point", "Polygon", "MultiPolygon")
        if f["geometry"]["type"] == "Point":
            lon, lat = f["geometry"]["coordinates"]
            assert np.isfinite([lon, lat]).all() and -180 <= lon <= 180 and -90 <= lat <= 90


def test_geojson_validity_and_deterministic_pagination(client):
    c = client
    for url in ("/api/clusters", "/api/clusters/geometries", "/api/density?cell=1000", f"/api/results/{EXP}/clusters",
                "/api/records/clusters?boroughs=MANHATTAN", f"/api/results/{EXP}/density?cell=1000"):
        _valid_fc(c.get(url).json())
    meta = c.get("/api/meta").json()
    bbox = "{:.4f},{:.4f},{:.4f},{:.4f}"
    pts = c.get("/api/points?bbox=-74.02,40.70,-73.98,40.74&limit=20000").json()
    if pts["total_locations"] < 2:
        lon, lat = c.get("/api/clusters").json()["features"][0]["geometry"]["coordinates"]
        b = bbox.format(lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02)
    else:
        b = "-74.02,40.70,-73.98,40.74"
    assert meta["limits"]["max_point_limit"] >= 1
    for base in ("/api/points", "/api/records/points", f"/api/results/{EXP}/points"):
        full = c.get(f"{base}?bbox={b}&limit=20000").json()
        _valid_fc(full)
        n = full["total_locations"]
        pages, off = [], 0
        while off is not None and n:
            page = c.get(f"{base}?bbox={b}&limit=2&offset={off}").json()
            assert page["total_locations"] == n and page["limit"] == 2           # toplam ≠ gösterilen; ayrı alanlar
            pages += [f["properties"]["location_id"] for f in page["features"]]
            off = page["next_offset"]
        assert pages == [f["properties"]["location_id"] for f in full["features"]] and len(set(pages)) == n
        assert full["truncated"] is False and full["returned_locations"] == n


# ----------------------------------------------------------------------------- API güvenliği
def test_api_input_validation_and_security_boundaries(client):
    c = client
    bad = [
        ("/api/records/points?bbox=-74,40.7,-73.99", 422), ("/api/records/points?bbox=nan,40,-73,41", 422),
        ("/api/records/points?bbox=-73,40,-74,41", 422), ("/api/records/points?bbox=-74,40,-73.99,40.01&limit=0", 422),
        ("/api/records/points?bbox=-74,40,-73.99,40.01&limit=999999", 422),
        ("/api/records/points?bbox=-74,40,-73.99,40.01&offset=-1", 422),
        ("/api/records/summary?date_from=0001-01-01", 422), ("/api/records/summary?years=99999", 422),
        ("/api/records/summary?hour_from=-1&hour_to=3", 422), ("/api/records/density?cell=-5", 422),
        ("/api/results/..%2F..%2Fetc/summary", 404), ("/api/results/lab-..%5Cx/summary", 404),
        ("/api/results/DBSCAN-ÜÇ/summary", 404), ("/api/lab/jobs/..%2Fjobs", 404), ("/api/lab/jobs/ZZZZZZZZZZZZ", 404),
        (f"/api/results/{EXP}/table?limit=100000", 422), (f"/api/results/{EXP}/timeline?granularity=minute", 422),
    ]
    for url, code in bad:
        r = c.get(url)
        assert r.status_code == code, (url, r.status_code, r.text[:200])
        assert "Traceback" not in r.text and "C:\\" not in r.text
    invalid = [
        {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": -5, "min_samples": 5}},
        {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 1e9, "min_samples": 5}},
        {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": "nan", "min_samples": 5}},
        {"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 1}},
        {"algorithm": "kmeans", "feature_set": "spatial_projected", "params": {"k": 3, "evil": 1}},
        {"algorithm": "hdbscan", "feature_set": "spatial_projected", "params": {"min_cluster_size": 5},
         "sample": {"n": 10}},
        {"algorithm": "rm -rf", "feature_set": "spatial_haversine", "params": {}},
    ]
    for body in invalid:
        assert c.post("/api/lab/jobs", json=body).status_code == 422, body
    assert c.post("/api/lab/jobs", content=b"x" * 70_000, headers={"content-type": "application/json"}).status_code == 413
    # DNS yeniden bağlama koruması: bilinmeyen Host reddedilir
    assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 400
    h = c.get("/api/health")
    assert h.headers["x-content-type-options"] == "nosniff" and h.headers["x-frame-options"] == "DENY"
    assert "access-control-allow-origin" not in h.headers
    assert c.get("/api/health", headers={"origin": "http://evil.example"}).headers.get("access-control-allow-origin") is None


# ----------------------------------------------------------------------------- gerçek veri (varsa)
@pytest.fixture(scope="module")
def real():
    from saferoute.analytics.catalog import Phase3Catalog
    from saferoute.analytics.events import EventStore
    from saferoute.clustering.data import processed_dir

    try:
        p = processed_dir()
    except Exception:
        pytest.skip("gerçek veri yok")
    if not (p / "phase3" / "experiments.json").exists() or not (p / "phase4" / "layer_manifest.json").exists():
        pytest.skip("Faz 3/4 çıktıları yok")
    lm = json.loads((p / "phase4" / "layer_manifest.json").read_text(encoding="utf-8"))
    store = EventStore.from_processed(p, p / "phase4", lm["model"]["experiment_id"])
    return p, store, Phase3Catalog(p / "phase3")


def test_real_saved_models_match_phase3_registry(real):
    from saferoute.analytics.results import LabelResult

    p, store, cat = real
    selected = cat.model_metadata["selected"]
    results = json.loads((p / "phase3" / "results.json").read_text(encoding="utf-8"))
    rows = {r["experiment_id"]: r for r in cat.experiments()}
    for algo in ("dbscan", "kmeans", "hdbscan"):
        eid = selected[algo]["experiment_id"]
        e = cat.by_id[eid]
        idx, lab = cat.load_event_labels(eid, store.n_events)
        r = LabelResult(store, idx, lab, algo, eid)
        s = r.summary()
        m = cat.experiment(eid)["metrics"]
        # Tam veride fit edilen modeller *_full, 100k örneklemde fit edilen HDBSCAN *_eval alanlarıyla eşleşmeli
        scope = "eval" if algo == "hdbscan" else "full"
        assert s["n_events"] == e["n_events"], algo
        assert s["n_clusters"] == m[f"n_clusters_{scope}"], algo
        assert s["largest_cluster_share"] == pytest.approx(m[f"largest_cluster_share_{scope}"], abs=1e-5), algo
        if algo == "kmeans":
            assert s["noise_ratio"] is None and not s["noise_applicable"]   # kayıttaki 0,0 "gürültü yok" DEĞİL, N/A
        else:
            assert s["noise_ratio"] == pytest.approx(m[f"noise_ratio_{scope}"], abs=1e-5), algo
        assert rows[eid]["params"] == {k: v for k, v in e["params"].items()}
        cov = r.coverage()
        assert cov["n_events"] == e["n_events"]
        if algo == "hdbscan":
            assert e["n_events"] == 100_000 and s["n_events"] < store.n_events  # örneklem kapsamı korunur
            assert r.density(1000)["total_events"] == 100_000             # tüm NYC gibi gösterilmez
        else:
            assert s["n_events"] == store.n_events
        tl = r.timeline("year")
        assert sum(b["count"] for b in tl["buckets"]) == e["n_events"]
        del r
    assert results  # Faz 3 sonuç dosyası okunabilir
