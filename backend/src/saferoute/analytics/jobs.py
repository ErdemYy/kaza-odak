"""Kümeleme Laboratuvarı iş yöneticisi.

* Her iş ayrı bir süreçte (``multiprocessing`` spawn) çalışır; API süreci ve UI iş parçacığı fit yapmaz.
* Aynı anda en fazla bir iş çalışır; en fazla ``max_pending`` iş kuyrukta bekler.
* Durumlar: ``pending`` → ``running`` → ``completed`` | ``failed`` | ``cancelled`` | ``rejected_resource``.
  ``running`` sırasında aşama (yükleme, kaynak ölçümü, fit, metrik, yazma) çalışanın yazdığı gerçek
  durum dosyasından okunur; yüzde tahmini üretilmez.
* Önbellek: istek + veri sürümü + kod sürümü anahtarıyla; tamamlanmış sonuç yeniden hesaplanmaz.
* Kayıtlı sonuç: filtresiz ve Faz 3 ızgarasındaki bir konfigürasyonla aynı istek, doğrulanmış Faz 3
  etiketlerinden yüklenir (yeniden fit yapılmaz) ve kaynak olarak deney kimliği gösterilir.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

from saferoute.analytics import lab_worker
from saferoute.analytics.catalog import Phase3Catalog
from saferoute.analytics.events import EventStore
from saferoute.analytics.lab_spec import BUDGET, FEATURE_SETS, LAB_CODE_VERSION, LabRequest
from saferoute.analytics.results import LabelResult

TERMINAL = ("completed", "failed", "cancelled", "rejected_resource")
# Faz 3 yapılandırmasındaki (backend/configs/phase3.toml) K-Means ve HDBSCAN deney ayarları
PHASE3_KMEANS = {"n_init": 10, "max_iter": 300, "random_state": 42}
PHASE3_HDBSCAN_SAMPLE = {"n": 100_000, "seed": 42}


class QueueFull(RuntimeError):
    pass


class EmptyScope(ValueError):
    pass


def sample_events(idx: np.ndarray, n: int, seed: int) -> np.ndarray:
    """Faz 3 ``subset_mask`` örneklemesiyle aynı: maskeli olaylardan yerine koymadan, sıralı."""
    if n >= len(idx):
        return idx
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(idx, size=n, replace=False))


class Job:
    def __init__(self, job_id: str, key: str, req: LabRequest, directory: Path):
        self.id = job_id
        self.key = key
        self.req = req
        self.dir = directory
        self.state = "pending"
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.error: str | None = None
        self.source = "dynamic"           # dynamic | cache | phase3_registry
        self.phase3_experiment: str | None = None
        self.n_events: int | None = None
        self.n_fit_rows: int | None = None
        self.worker: dict[str, Any] | None = None
        self.result: dict[str, Any] | None = None
        self.process: mp.process.BaseProcess | None = None
        self.cancel_requested = False

    def stage(self) -> dict[str, Any] | None:
        if self.state != "running":
            return None
        p = self.dir / "status.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"stage": "starting", "stage_label": "Süreç başlatılıyor"}

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        return {"job_id": self.id, "cache_key": self.key, "state": self.state, "stage": self.stage(),
                "request": self.req.to_dict(), "filters_tr": self.req.filters.describe_tr(),
                "feature_set": FEATURE_SETS[self.req.feature_set],
                "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
                "elapsed_s": round((self.finished_at or now) - (self.started_at or self.created_at), 2)
                if self.state != "pending" else None,
                "error": self.error, "source": self.source, "phase3_experiment": self.phase3_experiment,
                "n_events": self.n_events, "n_fit_rows": self.n_fit_rows, "worker": self.worker, "result": self.result,
                "code_version": LAB_CODE_VERSION}


class JobManager:
    def __init__(self, store: EventStore, catalog: Phase3Catalog | None, root: Path, dataset_version: str,
                 budget: dict[str, Any] | None = None, max_pending: int = 3, loc_rad: tuple[np.ndarray, np.ndarray] | None = None):
        self.store = store
        self.catalog = catalog
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.dataset_version = dataset_version
        self.budget = {**BUDGET, **(budget or {})}
        self.max_pending = max_pending
        self.jobs: OrderedDict[str, Job] = OrderedDict()
        self._results: OrderedDict[str, LabelResult] = OrderedDict()
        self._cv = threading.Condition()
        self._ctx = mp.get_context("spawn")
        # Faz 2 konum tablosundaki radyan değerleri (varsa) kullanılır: kayıtlı Faz 3 fit girdisiyle bit düzeyinde aynı
        self.loc_lat_rad, self.loc_lon_rad = loc_rad or store.loc_rad or (np.radians(store.loc_lat), np.radians(store.loc_lon))
        self._thread = threading.Thread(target=self._loop, name="saferoute-lab", daemon=True)
        self._stop = False
        self._thread.start()

    # ------------------------------------------------------------------ dış arayüz
    def submit(self, req: LabRequest) -> Job:
        mask = self.store.mask(req.filters)
        idx = np.flatnonzero(mask)
        if not len(idx):
            raise EmptyScope("Filtre sonucunda kayıt yok; kümeleme başlatılmadı.")
        key = req.cache_key(self.dataset_version)
        job = Job(uuid.uuid4().hex[:12], key, req, self.root / key)
        if req.sample:
            idx = sample_events(idx, req.sample["n"], req.sample["seed"])
        job.n_events = int(len(idx))
        with self._cv:
            # 1) Önbellek: aynı istek daha önce tamamlandı
            cached = self._load_cached(job)
            if cached:
                self._remember(job)
                return job
            # 2) Kayıtlı Faz 3 sonucu (yeniden fit yok)
            if self._try_registry(job):
                self._remember(job)
                return job
            # 3) Bütçe ön denetimi (fit başlamadan, anında)
            if reason := self._precheck(req, job.n_events):
                job.state, job.error, job.finished_at = "rejected_resource", reason, time.time()
                self._remember(job)
                return job
            pending = sum(1 for j in self.jobs.values() if j.state == "pending")
            if pending >= self.max_pending:
                raise QueueFull(f"Kuyrukta {pending} iş bekliyor; yeni iş için birinin bitmesini bekleyin veya iptal edin.")
            job.dir.mkdir(parents=True, exist_ok=True)
            np.save(job.dir / "event_index.npy", idx)
            self._remember(job)
            self._cv.notify_all()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        with self._cv:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            if job.state == "pending":
                job.state, job.finished_at, job.error = "cancelled", time.time(), "Kullanıcı iptal etti (başlamadan)."
            elif job.state == "running":
                job.cancel_requested = True
                if job.process is not None and job.process.is_alive():
                    job.process.terminate()
            self._cv.notify_all()
            return job

    def list(self) -> list[dict[str, Any]]:
        return [j.to_dict() | {"result": None} for j in reversed(self.jobs.values())]

    def result(self, job_id: str) -> LabelResult | None:
        job = self.jobs.get(job_id)
        if job is None or job.state != "completed":
            return None
        return self._label_result(job.key, lambda: self._read_labels(job), job.req.algorithm, f"lab-{job.key}")

    def registry_result(self, experiment_id: str) -> LabelResult:
        if self.catalog is None:
            raise FileNotFoundError("Faz 3 kaydı yüklenmedi")
        e = self.catalog.by_id.get(experiment_id)
        if e is None:
            raise KeyError(experiment_id)
        return self._label_result(f"p3:{experiment_id}", lambda: self.catalog.load_event_labels(experiment_id, self.store.n_events),
                                  e["algorithm"], experiment_id)

    def shutdown(self) -> None:
        with self._cv:
            self._stop = True
            for j in self.jobs.values():
                if j.process is not None and j.process.is_alive():
                    j.process.terminate()
            self._cv.notify_all()

    # ------------------------------------------------------------------ iç işler
    def _remember(self, job: Job) -> None:
        self.jobs[job.id] = job
        while len(self.jobs) > 200:
            old_id, old = next(iter(self.jobs.items()))
            if old.state not in TERMINAL:
                break
            self.jobs.pop(old_id)

    def _label_result(self, key: str, loader: Any, algorithm: str, rid: str) -> LabelResult:
        if key in self._results:
            self._results.move_to_end(key)
            return self._results[key]
        idx, lab = loader()
        r = LabelResult(self.store, idx, lab, algorithm, rid)
        self._results[key] = r
        while len(self._results) > 6:
            self._results.popitem(last=False)
        return r

    def _read_labels(self, job: Job) -> tuple[np.ndarray, np.ndarray]:
        if job.source == "phase3_registry" and job.phase3_experiment and self.catalog:
            return self.catalog.load_event_labels(job.phase3_experiment, self.store.n_events)
        z = np.load(job.dir / "labels.npz")
        return z["event_index"], z["labels"]

    def _load_cached(self, job: Job) -> bool:
        p = job.dir / "result.json"
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return False
        if data.get("cache_key") != job.key or data.get("state") != "completed":
            return False
        if data.get("source") != "phase3_registry" and not (job.dir / "labels.npz").exists():
            return False
        job.state, job.source = "completed", "cache"
        job.phase3_experiment = data.get("phase3_experiment")
        if data.get("source") == "phase3_registry":
            job.source = "phase3_registry"
        job.worker, job.result = data.get("worker"), data.get("result")
        job.n_fit_rows = data.get("n_fit_rows")
        job.started_at = job.finished_at = time.time()
        return True

    def _try_registry(self, job: Job) -> bool:
        req, cat = job.req, self.catalog
        if cat is None or not req.filters.is_empty():
            return False
        p = req.params
        e = None
        if req.algorithm == "dbscan" and req.feature_set == "spatial_haversine" and not req.sample:
            e = cat.find("dbscan", {"eps_m": p["eps_m"], "min_samples": p["min_samples"]})
        elif req.algorithm == "kmeans" and not req.sample and all(p[k] == v for k, v in PHASE3_KMEANS.items()):
            e = cat.find("kmeans", {"k": p["k"]})
        elif (req.algorithm == "hdbscan" and req.feature_set == "spatial_projected" and req.sample == PHASE3_HDBSCAN_SAMPLE
              and p.get("cluster_selection_method", "eom") == "eom"):
            e = cat.find("hdbscan", {"min_cluster_size": p["min_cluster_size"], "min_samples": p["min_samples"]},
                         scope_cls="sample")
        if e is None or cat.labels_path(e["experiment_id"]) is None:
            return False
        if e.get("dataset_version") != self.dataset_version:
            return False
        eid = e["experiment_id"]
        res = self.registry_result(eid)
        job.state, job.source, job.phase3_experiment = "completed", "phase3_registry", eid
        job.started_at = job.finished_at = time.time()
        job.n_fit_rows = e.get("n_unique_locations") if req.algorithm != "hdbscan" else e.get("n_events")
        job.worker = {"status": "completed", "runtime_s": e.get("runtime_s"), "peak_memory_mb": e.get("peak_memory_mb"),
                      "note": "Faz 3 deney kaydındaki ölçüm (yeniden fit yapılmadı)"}
        metrics = (cat.experiment(eid) or {}).get("metrics") or {}
        job.result = {"summary": res.summary(), "phase3_metrics": metrics}
        job.dir.mkdir(parents=True, exist_ok=True)
        self._write_result(job)
        return True

    def _precheck(self, req: LabRequest, n: int) -> str | None:
        b = self.budget
        if req.algorithm == "hdbscan" and n > b["max_hdbscan_events"]:
            return (f"Kaynak bütçesi: HDBSCAN kayıt düzeyidir ve ~karesel ölçeklenir. Kapsamdaki {n:,} olay "
                    f"> {b['max_hdbscan_events']:,} sınırı. Bir örneklem boyutu seçin veya filtreyi daraltın.").replace(",", ".")
        if req.feature_set == "spatiotemporal" and n > b["max_st_events"]:
            return (f"Kaynak bütçesi: uzay-zaman DBSCAN kayıt düzeyidir. Kapsamdaki {n:,} olay > "
                    f"{b['max_st_events']:,} sınırı. Filtreyi daraltın veya örneklem seçin.").replace(",", ".")
        return None

    def _prepare_input(self, job: Job) -> None:
        req = job.req
        idx = np.load(job.dir / "event_index.npy")
        s = self.store
        loc = s.c.location[idx]
        weighted = (req.algorithm == "dbscan" and req.feature_set == "spatial_haversine") or req.algorithm == "kmeans"
        if weighted:
            rows, event_to_row, counts = np.unique(loc, return_inverse=True, return_counts=True)
            arrays = {"lat_rad": self.loc_lat_rad[rows], "lon_rad": self.loc_lon_rad[rows], "x": s.loc_x[rows],
                      "y": s.loc_y[rows], "weight": counts.astype(np.int64)}
        else:
            event_to_row = np.arange(len(idx))
            arrays = {"lat_rad": self.loc_lat_rad[loc], "lon_rad": self.loc_lon_rad[loc], "x": s.loc_x[loc],
                      "y": s.loc_y[loc], "days": s.c.days[idx], "weight": np.ones(len(idx), dtype=np.int64)}
        np.savez(job.dir / "input.npz", **arrays)
        np.save(job.dir / "event_to_row.npy", event_to_row.ravel())
        job.n_fit_rows = int(len(arrays["weight"]))
        (job.dir / "request.json").write_text(json.dumps({**req.to_dict(), "budget": self.budget}, ensure_ascii=False),
                                              encoding="utf-8")

    def _write_result(self, job: Job, state: str | None = None) -> None:
        data = {"cache_key": job.key, "state": state or job.state, "source": job.source, "phase3_experiment": job.phase3_experiment,
                "request": job.req.to_dict(), "worker": job.worker, "result": job.result, "n_fit_rows": job.n_fit_rows,
                "n_events": job.n_events, "dataset_version": self.dataset_version, "code_version": LAB_CODE_VERSION,
                "finished_at": job.finished_at}
        (job.dir / "result.json").write_text(json.dumps(data, ensure_ascii=False, default=float), encoding="utf-8")

    def _loop(self) -> None:
        while True:
            with self._cv:
                while not self._stop and not any(j.state == "pending" for j in self.jobs.values()):
                    self._cv.wait(timeout=1.0)
                if self._stop:
                    return
                job = next(j for j in self.jobs.values() if j.state == "pending")
                job.state, job.started_at = "running", time.time()
            try:
                self._run(job)
            except Exception as exc:  # beklenmeyen ebeveyn hatası: iş başarısız, döngü sürer
                job.state, job.error, job.finished_at = "failed", f"{type(exc).__name__}: {exc}", time.time()

    def _run(self, job: Job) -> None:
        for f in ("status.json", "worker.json", "output.npz"):
            (job.dir / f).unlink(missing_ok=True)
        self._prepare_input(job)
        proc = self._ctx.Process(target=lab_worker.run_job, args=(str(job.dir),), daemon=True)
        with self._cv:
            if job.cancel_requested:
                job.state, job.finished_at, job.error = "cancelled", time.time(), "Kullanıcı iptal etti."
                return
            job.process = proc
            proc.start()
        deadline = time.time() + self.budget["timeout_s"]
        while proc.is_alive():
            proc.join(timeout=0.25)
            if time.time() > deadline and proc.is_alive():
                proc.terminate()
                proc.join(5)
                job.state, job.finished_at = "failed", time.time()
                job.error = f"Zaman aşımı: {self.budget['timeout_s']} sn içinde tamamlanmadı; süreç sonlandırıldı."
                return
        job.process = None
        if job.cancel_requested:
            job.state, job.finished_at, job.error = "cancelled", time.time(), "Kullanıcı iptal etti; süreç sonlandırıldı."
            return
        wp = job.dir / "worker.json"
        if not wp.exists():
            job.state, job.finished_at = "failed", time.time()
            job.error = f"Çalışan süreç beklenmedik şekilde sonlandı (çıkış kodu {proc.exitcode})."
            return
        w = json.loads(wp.read_text(encoding="utf-8"))
        job.worker = {k: v for k, v in w.items() if k != "traceback"}
        if w["status"] != "completed":
            job.state, job.error, job.finished_at = w["status"], w.get("error"), time.time()
            return
        row_labels = np.load(job.dir / "output.npz")["labels"]
        idx = np.load(job.dir / "event_index.npy")
        e2r = np.load(job.dir / "event_to_row.npy")
        labels = row_labels[e2r].astype(np.int32)
        np.savez_compressed(job.dir / "labels.npz", event_index=idx, labels=labels)
        for f in ("input.npz", "output.npz", "event_to_row.npy"):
            (job.dir / f).unlink(missing_ok=True)
        res = self._label_result(job.key, lambda: (idx, labels), job.req.algorithm, f"lab-{job.key}")
        job.result = {"summary": res.summary(), "metrics": w.get("metrics")}
        job.finished_at = time.time()
        # Önce önbellek dosyası, sonra durum: "completed" görülen her iş önbellekten yeniden bulunabilir.
        self._write_result(job, state="completed")
        job.state = "completed"

    def clear_cache(self) -> int:
        n = 0
        for d in self.root.iterdir():
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n
