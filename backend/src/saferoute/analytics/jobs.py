"""Kümeleme Laboratuvarı iş yöneticisi (Faz 6: kalıcı).

* İş meta verisi SQLite'ta tutulur (``jobstore.JobStore``); sunucu yeniden başlasa da iş geçmişi ve durumlar
  kaybolmaz. Hesaplama sonuçları iş dizinindeki dosyalardadır (``labels.npz`` + ``result.json``, SHA-256'lı).
* Durumlar: ``queued`` → ``running`` → ``completed`` | ``failed`` | ``cancelled`` | ``interrupted`` |
  ``resource_limited``. Geçişler karşılaştır-ve-değiştir ile atomiktir.
* **Yeniden başlatma uzlaştırması:** açılışta ``queued``/``running`` kalan işler incelenir. Sonuç dosyaları
  eksiksiz ve doğrulanmışsa iş ``completed`` (kurtarıldı) olur; aksi hâlde ``interrupted``. Yarım kalan işler
  KENDİLİĞİNDEN yeniden çalıştırılmaz; kullanıcı ``retry`` ile açıkça yeni bir iş başlatır.
* Her iş ayrı bir süreçte (``multiprocessing`` spawn) çalışır; Windows'ta iş nesnesiyle (KILL_ON_JOB_CLOSE +
  bellek tavanı) korunur. Aynı anda en fazla ``max_concurrent`` (varsayılan 1) iş çalışır; en fazla
  ``max_pending`` iş kuyrukta bekler. Başlatmadan önce boş fiziksel bellek ölçülür.
* ``running`` sırasında aşama çalışanın yazdığı gerçek durum dosyasından okunur; yüzde tahmini üretilmez.
* Önbellek: istek + veri sürümü + kod sürümü anahtarıyla; tamamlanmış sonuç yeniden hesaplanmaz.
* Kayıtlı sonuç: filtresiz ve Faz 3 ızgarasındaki bir konfigürasyonla aynı istek, doğrulanmış Faz 3
  etiketlerinden yüklenir (yeniden fit yapılmaz) ve kaynak olarak deney kimliği gösterilir.
* Deney kimliği: kayıtlı sonuçta Faz 3 deney kimliği, dinamik sonuçta ``dyn-<önbellek anahtarı>``. Farklı
  deneylerin küme numaraları eşleştirilmez.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

from saferoute.analytics import lab_worker, procguard
from saferoute.analytics.catalog import Phase3Catalog
from saferoute.analytics.events import EventStore
from saferoute.analytics.filters import FilterSpec
from saferoute.analytics.jobstore import ACTIVE, RETRYABLE, TERMINAL, JobStore
from saferoute.analytics.lab_spec import BUDGET, FEATURE_SETS, LAB_CODE_VERSION, LabRequest, LabRequestError, validate_request
from saferoute.analytics.results import LabelResult
from saferoute.perf import available_memory_mb

# Faz 3 yapılandırmasındaki (backend/configs/phase3.toml) K-Means ve HDBSCAN deney ayarları
PHASE3_KMEANS = {"n_init": 10, "max_iter": 300, "random_state": 42}
PHASE3_HDBSCAN_SAMPLE = {"n": 100_000, "seed": 42}
MONITOR_INTERVAL_S = 0.25


class QueueFull(RuntimeError):
    pass


class EmptyScope(ValueError):
    pass


class NotRetryable(ValueError):
    pass


def sample_events(idx: np.ndarray, n: int, seed: int) -> np.ndarray:
    """Faz 3 ``subset_mask`` örneklemesiyle aynı: maskeli olaylardan yerine koymadan, sıralı."""
    if n >= len(idx):
        return idx
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(idx, size=n, replace=False))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dynamic_experiment_id(cache_key: str) -> str:
    return f"dyn-{cache_key}"


class Job:
    """Bir işin bellekteki görünümü. Kalıcı kopya ``JobStore``'dadır; her değişiklik oraya yazılır."""

    def __init__(self, job_id: str, key: str, req: LabRequest, directory: Path):
        self.id = job_id
        self.key = key
        self.req = req
        self.dir = directory
        self.state = "queued"
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.error: str | None = None
        self.error_kind: str | None = None
        self.source = "dynamic"           # dynamic | cache | phase3_registry
        self.phase3_experiment: str | None = None
        self.n_events: int | None = None
        self.n_fit_rows: int | None = None
        self.worker: dict[str, Any] | None = None
        self.result: dict[str, Any] | None = None
        self.process: mp.process.BaseProcess | None = None
        self.cancel_requested = False
        self.retry_of: str | None = None
        self.recovered = False
        self.output_sha256: str | None = None
        self.filters_tr: list[str] = req.filters.describe_tr()
        self.worker_pid: int | None = None

    @property
    def experiment_id(self) -> str:
        return self.phase3_experiment if self.source == "phase3_registry" and self.phase3_experiment \
            else dynamic_experiment_id(self.key)

    def stage(self) -> dict[str, Any] | None:
        if self.state != "running":
            return None
        p = self.dir / "status.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"stage": "starting", "stage_label": "Süreç başlatılıyor"}

    def record(self) -> dict[str, Any]:
        """Kalıcı kayıt alanları."""
        out = self.dir / "labels.npz"
        return {"job_id": self.id, "experiment_id": self.experiment_id, "cache_key": self.key,
                "algorithm": self.req.algorithm, "feature_set": self.req.feature_set, "params": self.req.params,
                "filters": self.req.filters.to_dict(), "sample": self.req.sample, "request": self.req.to_dict(),
                "filters_tr": self.filters_tr, "state": self.state, "submitted_at": self.created_at,
                "started_at": self.started_at, "finished_at": self.finished_at, "error": self.error,
                "error_kind": self.error_kind, "output_path": str(out) if self.state == "completed" else None,
                "output_sha256": self.output_sha256, "source": self.source, "phase3_experiment": self.phase3_experiment,
                "n_events": self.n_events, "n_fit_rows": self.n_fit_rows, "worker": self.worker, "result": self.result,
                "retry_of": self.retry_of, "recovered": int(self.recovered)}

    @classmethod
    def from_record(cls, rec: dict[str, Any], root: Path) -> "Job":
        try:
            req = validate_request(rec["request"])
        except LabRequestError:
            # Kod sürümü değişip istek artık geçersizse bile geçmiş kayıt gösterilebilsin
            r = rec["request"]
            req = LabRequest(algorithm=r["algorithm"], feature_set=r["feature_set"], params=r["params"],
                             filters=FilterSpec(), sample=r.get("sample"))
        job = cls(rec["job_id"], rec["cache_key"], req, root / rec["cache_key"])
        job.filters_tr = rec.get("filters_tr") or job.filters_tr
        for a, k in (("state", "state"), ("created_at", "submitted_at"), ("started_at", "started_at"),
                     ("finished_at", "finished_at"), ("error", "error"), ("error_kind", "error_kind"),
                     ("source", "source"), ("phase3_experiment", "phase3_experiment"), ("n_events", "n_events"),
                     ("n_fit_rows", "n_fit_rows"), ("worker", "worker"), ("result", "result"), ("retry_of", "retry_of"),
                     ("recovered", "recovered"), ("output_sha256", "output_sha256")):
            setattr(job, a, rec.get(k))
        job.recovered = bool(job.recovered)
        return job

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        return {"job_id": self.id, "experiment_id": self.experiment_id, "cache_key": self.key, "state": self.state,
                "stage": self.stage(), "request": self.req.to_dict(), "filters_tr": self.filters_tr,
                "feature_set": FEATURE_SETS[self.req.feature_set],
                "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
                "elapsed_s": round((self.finished_at or now) - (self.started_at or self.created_at), 2)
                if self.state != "queued" else None,
                "error": self.error, "error_kind": self.error_kind, "source": self.source,
                "phase3_experiment": self.phase3_experiment, "n_events": self.n_events, "n_fit_rows": self.n_fit_rows,
                "worker": self.worker, "result": self.result, "retry_of": self.retry_of, "recovered": self.recovered,
                "retryable": self.state in RETRYABLE, "output_sha256": self.output_sha256,
                "worker_pid": self.worker_pid if self.state == "running" else None,
                "code_version": LAB_CODE_VERSION}


class JobManager:
    def __init__(self, store: EventStore, catalog: Phase3Catalog | None, root: Path, dataset_version: str,
                 budget: dict[str, Any] | None = None, max_pending: int = 3, max_concurrent: int = 1,
                 loc_rad: tuple[np.ndarray, np.ndarray] | None = None, memory_probe: Any = None):
        self.store = store
        self.catalog = catalog
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.dataset_version = dataset_version
        self.budget = {**BUDGET, **(budget or {})}
        self.max_pending = max_pending
        self.max_concurrent = max_concurrent
        self.memory_probe = memory_probe or available_memory_mb  # testlerde kaynak kıtlığı taklit edilebilir
        self.server_id = uuid.uuid4().hex[:8]
        # Çalışan süreçlerin BLAS/OpenMP iş parçacığı sayısı sınırlanır: OpenBLAS her iş parçacığı için arabellek
        # ayırır (16 mantıksal çekirdekte ölçülen commit 1.376 MB, 4 iş parçacığıyla 475 MB; RSS ~160 MB).
        # Spawn edilen çocuk ortamı devralır; kullanıcı değişkeni önceden tanımladıysa ona dokunulmaz.
        threads = str(self.budget["worker_threads"])
        for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(var, threads)
        self.db = JobStore(self.root / "jobs.sqlite3")
        self.jobs: OrderedDict[str, Job] = OrderedDict()   # etkin + son kullanılan işler (önbellek)
        self._results: OrderedDict[str, LabelResult] = OrderedDict()
        self._cv = threading.Condition()
        self._ctx = mp.get_context("spawn")
        self.recovery = self._recover()
        # Faz 2 konum tablosundaki radyan değerleri (varsa) kullanılır: kayıtlı Faz 3 fit girdisiyle bit düzeyinde aynı
        self.loc_lat_rad, self.loc_lon_rad = loc_rad or store.loc_rad or (np.radians(store.loc_lat), np.radians(store.loc_lon))
        self._stop = False
        self._threads = [threading.Thread(target=self._loop, name=f"saferoute-lab-{i}", daemon=True)
                         for i in range(max_concurrent)]
        for t in self._threads:
            t.start()

    # ------------------------------------------------------------------ yeniden başlatma uzlaştırması
    def _recover(self) -> dict[str, Any]:
        """Önceki sunucu sürecinden kalan etkin işleri güvenle sonuçlandırır (yeniden ÇALIŞTIRMAZ)."""
        report: dict[str, Any] = {"checked": 0, "recovered_completed": [], "interrupted": [], "orphans_killed": [],
                                  "db_integrity": self.db.integrity()}
        for rec in self.db.list(limit=10_000, states=ACTIVE):
            report["checked"] += 1
            jid = rec["job_id"]
            if procguard.is_our_worker(rec.get("worker_pid"), rec.get("worker_create_time")):
                k = procguard.kill_tree(int(rec["worker_pid"]))
                report["orphans_killed"].append({"job_id": jid, "pid": rec["worker_pid"], **k})
            job = Job.from_record(rec, self.root)
            done = self._verified_result_file(job)
            if done is not None:
                fields = {"state": "completed", "recovered": 1, "finished_at": done.get("finished_at") or time.time(),
                          "worker": done.get("worker"), "result": done.get("result"), "n_fit_rows": done.get("n_fit_rows"),
                          "output_path": str(job.dir / "labels.npz"), "output_sha256": done.get("labels_sha256"),
                          "error": None, "error_kind": None}
                if self.db.update(jid, fields, expect=ACTIVE):
                    report["recovered_completed"].append(jid)
                continue
            if rec["state"] == "running":
                msg = ("Sunucu bu iş çalışırken kapandı. Yarım kalan hesaplama diske yazılmadığı için kurtarılamaz; "
                       "sonuç uydurulmadı. 'Yeniden dene' ile aynı isteği yeni bir iş olarak başlatabilirsiniz.")
            else:
                msg = ("Sunucu yeniden başladığında iş kuyrukta bekliyordu. Kontrolsüz yeniden çalıştırma yapılmadı; "
                       "'Yeniden dene' ile başlatabilirsiniz.")
            if self.db.update(jid, {"state": "interrupted", "finished_at": time.time(), "error": msg,
                                    "error_kind": "interrupted_restart", "worker_pid": None}, expect=ACTIVE):
                report["interrupted"].append(jid)
        return report

    def _verified_result_file(self, job: Job) -> dict[str, Any] | None:
        """İş dizininde eksiksiz ve doğrulanmış bir 'completed' sonucu varsa onu döndürür."""
        p = job.dir / "result.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if data.get("cache_key") != job.key or data.get("state") != "completed":
            return None
        if data.get("dataset_version") != self.dataset_version or data.get("code_version") != LAB_CODE_VERSION:
            return None
        if data.get("source") == "phase3_registry":
            return data
        lp = job.dir / "labels.npz"
        if not lp.exists():
            return None
        sha = data.get("labels_sha256")
        if sha and sha256_file(lp) != sha:
            return None  # bozuk/eksik çıktı: kullanılmaz, yeniden hesaplanır
        return data

    # ------------------------------------------------------------------ dış arayüz
    def submit(self, req: LabRequest, retry_of: str | None = None) -> Job:
        mask = self.store.mask(req.filters)
        idx = np.flatnonzero(mask)
        if not len(idx):
            raise EmptyScope("Filtre sonucunda kayıt yok; kümeleme başlatılmadı.")
        key = req.cache_key(self.dataset_version)
        job = Job(uuid.uuid4().hex[:12], key, req, self.root / key)
        job.retry_of = retry_of
        if req.sample:
            idx = sample_events(idx, req.sample["n"], req.sample["seed"])
        job.n_events = int(len(idx))
        with self._cv:
            # 0) Aynı istek zaten kuyrukta/çalışıyor: ikinci kopya açılmaz (aynı dizine eşzamanlı yazma yarışı yok)
            dup = self.db.active_with_key(key)
            if dup is not None:
                return self.get(dup["job_id"]) or job
            # 1) Önbellek: aynı istek daha önce tamamlandı
            if self._load_cached(job):
                return self._insert(job)
            # 2) Kayıtlı Faz 3 sonucu (yeniden fit yok)
            if self._try_registry(job):
                return self._insert(job)
            # 3) Bütçe ve kaynak ön denetimi (fit başlamadan, anında)
            if reason := self._precheck(req, job.n_events):
                job.state, job.error, job.error_kind, job.finished_at = "resource_limited", reason[1], reason[0], time.time()
                return self._insert(job)
            pending = self.db.count(("queued",))
            if pending >= self.max_pending:
                raise QueueFull(f"Kuyrukta {pending} iş bekliyor; yeni iş için birinin bitmesini bekleyin veya iptal edin.")
            job.dir.mkdir(parents=True, exist_ok=True)
            np.save(job.dir / "event_index.npy", idx)
            self._insert(job)
            self._cv.notify_all()
        return job

    def retry(self, job_id: str, factors: set[str] | None = None) -> Job:
        """Yarım kalmış / başarısız / iptal edilmiş bir işi AÇIK kullanıcı isteğiyle yeni iş olarak başlatır."""
        rec = self.db.get(job_id)
        if rec is None:
            raise KeyError(job_id)
        if rec["state"] not in RETRYABLE:
            raise NotRetryable(f"Bu iş yeniden denenemez (durum: {rec['state']}).")
        req = validate_request(rec["request"], factors)  # güncel kurallarla yeniden doğrulanır
        return self.submit(req, retry_of=job_id)

    def get(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is not None:
            return job
        rec = self.db.get(job_id)
        if rec is None:
            return None
        job = Job.from_record(rec, self.root)
        self._cache(job)
        return job

    def by_experiment(self, experiment_id: str) -> Job | None:
        rec = self.db.latest_completed(experiment_id)
        return self.get(rec["job_id"]) if rec else None

    def cancel(self, job_id: str) -> Job | None:
        with self._cv:
            job = self.get(job_id)
            if job is None:
                return None
            if job.state == "queued":
                self._finish(job, "cancelled", "Kullanıcı iptal etti (başlamadan).", "user_cancel", expect=("queued",))
            elif job.state == "running":
                job.cancel_requested = True
                proc = job.process
                kill = procguard.kill_tree(proc.pid) if proc is not None and proc.pid else {"verified": True, "killed": 0}
                msg = ("Kullanıcı iptal etti; çalışan süreç sonlandırıldı ve sonlandığı doğrulandı." if kill.get("verified")
                       else "Kullanıcı iptal etti; süreç sonlandırma isteği gönderildi ancak doğrulanamadı.")
                job.worker = {**(job.worker or {}), "termination": kill}
                self._finish(job, "cancelled", msg, "user_cancel", expect=("running",))
            self._cv.notify_all()
            return job

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        out = []
        for rec in self.db.list(limit=limit):
            j = self.jobs.get(rec["job_id"]) or Job.from_record(rec, self.root)
            out.append(j.to_dict() | {"result": None})
        return out

    def result(self, job_id: str) -> LabelResult | None:
        job = self.get(job_id)
        if job is None or job.state != "completed":
            return None
        return self._label_result(job.key, lambda: self._read_labels(job), job.req.algorithm, f"lab-{job.id}")

    def registry_result(self, experiment_id: str) -> LabelResult:
        if self.catalog is None:
            raise FileNotFoundError("Faz 3 kaydı yüklenmedi")
        e = self.catalog.by_id.get(experiment_id)
        if e is None:
            raise KeyError(experiment_id)
        return self._label_result(f"p3:{experiment_id}", lambda: self.catalog.load_event_labels(experiment_id, self.store.n_events),
                                  e["algorithm"], experiment_id)

    def resources(self) -> dict[str, Any]:
        free = self.memory_probe()
        return {"available_memory_mb": free, "min_free_memory_mb": self.budget["min_free_memory_mb"],
                "can_start": free is None or free >= self.budget["min_free_memory_mb"],
                "worker_memory_limit_mb": self._worker_limit(free), "max_concurrent": self.max_concurrent,
                "max_pending": self.max_pending, "running": self.db.count(("running",)), "queued": self.db.count(("queued",)),
                "job_object": os.name == "nt", "cpu_count": os.cpu_count()}

    def shutdown(self) -> None:
        """Sunucu kapanışı: çalışan işler sonlandırılır ve ``interrupted`` işaretlenir; kuyruktakiler başlatılmaz."""
        with self._cv:
            self._stop = True
            for j in list(self.jobs.values()):
                if j.state == "running":
                    j.cancel_requested = True
                    kill = procguard.kill_tree(j.process.pid) if j.process is not None and j.process.pid else {"verified": True}
                    j.worker = {**(j.worker or {}), "termination": kill}
                    self._finish(j, "interrupted", "Sunucu kapatıldığı için iş yarıda kesildi; sonuç yazılmadı. "
                                 "'Yeniden dene' ile yeniden başlatabilirsiniz.", "interrupted_shutdown", expect=("running",))
            for rec in self.db.list(limit=10_000, states=("queued",)):
                self.db.update(rec["job_id"], {"state": "interrupted", "finished_at": time.time(),
                                               "error": "Sunucu kapatıldığında iş kuyrukta bekliyordu; başlatılmadı.",
                                               "error_kind": "interrupted_shutdown"}, expect=("queued",))
                if rec["job_id"] in self.jobs:
                    self.jobs[rec["job_id"]].state = "interrupted"
            self._cv.notify_all()

    # ------------------------------------------------------------------ iç işler
    def _cache(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.jobs.move_to_end(job.id)
        while len(self.jobs) > 200:
            old_id, old = next(iter(self.jobs.items()))
            if old.state not in TERMINAL:
                break
            self.jobs.pop(old_id)

    def _insert(self, job: Job) -> Job:
        self.db.insert({**job.record(), "server_id": self.server_id})
        self._cache(job)
        return job

    def _persist(self, job: Job, expect: tuple[str, ...] | None = None) -> bool:
        rec = job.record()
        rec.pop("job_id")
        return self.db.update(job.id, rec, expect=expect)

    def _finish(self, job: Job, state: str, error: str | None, kind: str | None, expect: tuple[str, ...]) -> bool:
        """Atomik son durum geçişi. Başka bir yol (iptal/kapanış) durumu önce değiştirdiyse yazmaz."""
        fields = {"state": state, "error": _sanitize(error, self.root), "error_kind": kind, "finished_at": time.time(),
                  "worker": job.worker, "worker_pid": None}
        if not self.db.update(job.id, fields, expect=expect):
            rec = self.db.get(job.id)
            if rec:
                job.state, job.error, job.error_kind = rec["state"], rec["error"], rec["error_kind"]
            return False
        job.state, job.error, job.error_kind, job.finished_at = state, fields["error"], kind, fields["finished_at"]
        return True

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
        lp = job.dir / "labels.npz"
        if job.output_sha256 and sha256_file(lp) != job.output_sha256:
            raise ValueError(f"Sonuç dosyası değişmiş (SHA-256 uyuşmuyor): {job.experiment_id}")
        z = np.load(lp)
        idx, lab = z["event_index"], z["labels"]
        if len(idx) and (int(idx.max()) >= self.store.n_events or int(idx.min()) < 0):
            raise ValueError(f"Sonuçtaki olay indeksi veri kapsamı dışında: {job.experiment_id}")
        return idx, lab

    def _load_cached(self, job: Job) -> bool:
        data = self._verified_result_file(job)
        if data is None:
            return False
        job.state, job.source = "completed", "cache"
        job.phase3_experiment = data.get("phase3_experiment")
        if data.get("source") == "phase3_registry":
            job.source = "phase3_registry"
        job.worker, job.result = data.get("worker"), data.get("result")
        job.n_fit_rows = data.get("n_fit_rows")
        job.output_sha256 = data.get("labels_sha256")
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

    def _precheck(self, req: LabRequest, n: int) -> tuple[str, str] | None:
        b = self.budget
        if req.algorithm == "hdbscan" and n > b["max_hdbscan_events"]:
            return "resource_budget", (f"Kaynak bütçesi: HDBSCAN kayıt düzeyidir ve ~karesel ölçeklenir. Kapsamdaki {n:,} olay "
                                       f"> {b['max_hdbscan_events']:,} sınırı. Bir örneklem boyutu seçin veya filtreyi daraltın.").replace(",", ".")
        if req.feature_set == "spatiotemporal" and n > b["max_st_events"]:
            return "resource_budget", (f"Kaynak bütçesi: uzay-zaman DBSCAN kayıt düzeyidir. Kapsamdaki {n:,} olay > "
                                       f"{b['max_st_events']:,} sınırı. Filtreyi daraltın veya örneklem seçin.").replace(",", ".")
        free = self.memory_probe()
        if free is not None and free < b["min_free_memory_mb"]:
            return "resource_memory", (f"Bellek yetersiz: kullanılabilir fiziksel bellek {free:,.0f} MB < gereken "
                                       f"{b['min_free_memory_mb']:,} MB. Diğer uygulamaları kapatıp yeniden deneyin; iş başlatılmadı."
                                       ).replace(",", ".")
        return None

    def _worker_limit(self, free: float | None) -> int:
        """Çalışan için sert bellek tavanı (MB): bütçe üst sınırı ile 'boş bellek − güvenlik payı'nın küçüğü."""
        cap = int(self.budget["max_worker_memory_mb"])
        if free is None:
            return cap
        return int(max(self.budget["min_worker_memory_mb"], min(cap, free - self.budget["memory_headroom_mb"])))

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
                "experiment_id": job.experiment_id, "request": job.req.to_dict(), "worker": job.worker, "result": job.result,
                "n_fit_rows": job.n_fit_rows, "n_events": job.n_events, "dataset_version": self.dataset_version,
                "code_version": LAB_CODE_VERSION, "finished_at": job.finished_at, "labels_sha256": job.output_sha256}
        lab_worker._write_json(job.dir / "result.json", data)

    def _next_queued(self) -> Job | None:
        for rec in reversed(self.db.list(limit=50, states=("queued",))):
            job = self.get(rec["job_id"])
            if job is not None and job.state == "queued":
                return job
        return None

    def _loop(self) -> None:
        while True:
            with self._cv:
                job = None
                while not self._stop and (job := self._next_queued()) is None:
                    self._cv.wait(timeout=1.0)
                if self._stop or job is None:
                    return
                job.state, job.started_at = "running", time.time()
                if not self._persist(job, expect=("queued",)):
                    continue  # bu arada iptal edildi
            try:
                self._run(job)
            except Exception as exc:  # beklenmeyen ebeveyn hatası: iş başarısız, döngü sürer
                self._finish(job, "failed", f"{type(exc).__name__}: {exc}", "server_error", expect=("running",))

    def _run(self, job: Job) -> None:
        # Bu arada aynı istek başka bir yoldan tamamlanmış olabilir
        if (data := self._verified_result_file(job)) is not None and data.get("source") != "phase3_registry":
            job.source, job.worker, job.result = "cache", data.get("worker"), data.get("result")
            job.n_fit_rows, job.output_sha256 = data.get("n_fit_rows"), data.get("labels_sha256")
            job.finished_at, job.state = time.time(), "completed"
            self._persist(job, expect=("running",))
            return
        for f in ("status.json", "worker.json", "output.npz", "labels.npz", "result.json"):
            (job.dir / f).unlink(missing_ok=True)
        self._prepare_input(job)
        free = self.memory_probe()
        if free is not None and free < self.budget["min_free_memory_mb"]:
            self._finish(job, "resource_limited", f"Bellek yetersiz: başlatma anında boş fiziksel bellek {free:.0f} MB < "
                         f"{self.budget['min_free_memory_mb']} MB. Süreç başlatılmadı.", "resource_memory", expect=("running",))
            return
        limit_mb = self._worker_limit(free)
        proc = self._ctx.Process(target=lab_worker.run_job, args=(str(job.dir),), daemon=True)
        with self._cv:
            if job.cancel_requested or job.state != "running":
                return
            proc.start()
            job.process = proc
            job.worker_pid = proc.pid
        guard = procguard.WorkerGuard(proc.pid, limit_mb)
        sampler = procguard.Sampler(proc.pid)
        self.db.update(job.id, {"worker_pid": proc.pid, "worker_create_time": procguard.create_time(proc.pid)})
        deadline = time.time() + self.budget["timeout_s"]
        watchdog: str | None = None
        while proc.is_alive():
            proc.join(timeout=MONITOR_INTERVAL_S)
            rss = sampler.sample()
            if rss is not None and not guard.attached and rss > limit_mb:
                # İş nesnesi yoksa (Windows dışı) yazılımsal bekçi: tavanı aşan çalışan sonlandırılır
                watchdog = f"Çalışan bellek tavanını aştı ({rss:.0f} MB > {limit_mb} MB); süreç sonlandırıldı."
                procguard.kill_tree(proc.pid)
            if time.time() > deadline and proc.is_alive():
                watchdog = f"Zaman aşımı: {self.budget['timeout_s']} sn içinde tamamlanmadı; süreç sonlandırıldı."
                procguard.kill_tree(proc.pid)
        peak_commit = guard.peak_commit_mb()
        guard.close()
        job.process = None
        monitor = {**sampler.summary(), "peak_commit_mb": peak_commit, "available_memory_mb_at_start": free,
                   "guard": guard.describe(), "exit_code": proc.exitcode}
        job.worker = {**(job.worker or {}), "monitor": monitor}
        if job.cancel_requested or job.state != "running":
            self.db.update(job.id, {"worker": job.worker})
            return
        if watchdog:
            self._finish(job, "resource_limited", watchdog, "timeout" if "Zaman" in watchdog else "resource_memory",
                         expect=("running",))
            return
        wp = job.dir / "worker.json"
        if not wp.exists():
            near_limit = peak_commit is not None and peak_commit >= 0.95 * limit_mb
            if near_limit:
                self._finish(job, "resource_limited", f"Çalışan bellek tavanına ({limit_mb} MB) ulaştı ve sonlandı "
                             f"(tepe {peak_commit:.0f} MB). Kapsamı daraltın veya örneklem kullanın.", "resource_memory",
                             expect=("running",))
            else:
                self._finish(job, "failed", f"Çalışan süreç beklenmedik şekilde sonlandı (çıkış kodu {proc.exitcode}).",
                             "worker_crash", expect=("running",))
            return
        w = json.loads(wp.read_text(encoding="utf-8"))
        job.worker = {**{k: v for k, v in w.items() if k != "traceback"}, "monitor": monitor}
        if w["status"] != "completed":
            state = "resource_limited" if w["status"] in ("rejected_resource", "resource_limited") else "failed"
            kind = "resource_memory" if "MemoryError" in (w.get("error") or "") else (
                "resource_budget" if state == "resource_limited" else "worker_error")
            self._finish(job, state, w.get("error"), kind, expect=("running",))
            return
        row_labels = np.load(job.dir / "output.npz")["labels"]
        idx = np.load(job.dir / "event_index.npy")
        e2r = np.load(job.dir / "event_to_row.npy")
        labels = row_labels[e2r].astype(np.int32)
        np.savez_compressed(job.dir / "labels.npz", event_index=idx, labels=labels)
        job.output_sha256 = sha256_file(job.dir / "labels.npz")
        for f in ("input.npz", "output.npz", "event_to_row.npy"):
            (job.dir / f).unlink(missing_ok=True)
        res = self._label_result(job.key, lambda: (idx, labels), job.req.algorithm, f"lab-{job.id}")
        job.result = {"summary": res.summary(), "metrics": w.get("metrics")}
        job.finished_at = time.time()
        # Önce sonuç dosyası (SHA-256'lı), sonra kalıcı durum: "completed" görülen her iş diskten yeniden bulunabilir.
        self._write_result(job, state="completed")
        job.state = "completed"
        if not self._persist(job, expect=("running",)):
            # Bu arada iptal/kapanış: dosya diskte kalsa da durum geri alınmaz (bir sonraki aynı istek önbellekten alır)
            rec = self.db.get(job.id)
            job.state = rec["state"] if rec else job.state

    def clear_cache(self) -> int:
        n = 0
        for d in self.root.iterdir():
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n


def _sanitize(msg: str | None, lab_root: Path) -> str | None:
    """Kullanıcıya dönen hata metninden mutlak sistem yollarını çıkarır."""
    if not msg:
        return msg
    from saferoute import config

    for path, label in ((lab_root, "<lab_cache>"), (config.REPO_ROOT, "<proje>"), (Path.home(), "~")):
        for form in {str(path), str(path).replace("\\", "/"), str(path).replace("\\", "\\\\")}:
            msg = msg.replace(form, label)
    return msg[:1500]
