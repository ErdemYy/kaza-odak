"""Kümeleme Laboratuvarı için kalıcı iş kaydı (SQLite, WAL).

* Tek dosya (``<lab_root>/jobs.sqlite3``), ek sunucu gerektirmez; yerel geliştirme ve akademik demo içindir.
* Her güncelleme tek bir ``UPDATE`` deyimidir (otomatik işlem = atomik). Durum geçişleri karşılaştır-ve-değiştir
  (``WHERE state IN (...)``) ile yapılır: örneğin iptal edilmiş bir iş, geç gelen bir "tamamlandı" yazımıyla
  başarılı işaretlenemez.
* Hesaplama sonuçları burada değil, iş dizinindeki dosyalardadır (``labels.npz`` + ``result.json``); kayıt yalnızca
  meta veriyi ve çıktı yolunu tutar. Dosyaya yazılmamış bir hesaplama kurtarılmış sayılmaz.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1

STATES = ("queued", "running", "completed", "failed", "cancelled", "interrupted", "resource_limited")
ACTIVE = ("queued", "running")
TERMINAL = ("completed", "failed", "cancelled", "interrupted", "resource_limited")
RETRYABLE = ("failed", "cancelled", "interrupted", "resource_limited")

JSON_COLS = ("params", "filters", "sample", "request", "filters_tr", "worker", "result")
COLUMNS = (
    "job_id", "experiment_id", "cache_key", "algorithm", "feature_set", "params", "filters", "sample", "request",
    "filters_tr", "dataset_version", "code_version", "state", "submitted_at", "started_at", "finished_at", "error",
    "error_kind", "output_path", "output_sha256", "source", "phase3_experiment", "n_events", "n_fit_rows", "worker",
    "result", "worker_pid", "worker_create_time", "retry_of", "server_id", "recovered", "updated_at",
)

_DDL = f"""
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    feature_set TEXT NOT NULL,
    params TEXT, filters TEXT, sample TEXT, request TEXT NOT NULL, filters_tr TEXT,
    dataset_version TEXT, code_version TEXT,
    state TEXT NOT NULL CHECK (state IN ({", ".join(repr(s) for s in STATES)})),
    submitted_at REAL NOT NULL, started_at REAL, finished_at REAL,
    error TEXT, error_kind TEXT,
    output_path TEXT, output_sha256 TEXT,
    source TEXT, phase3_experiment TEXT,
    n_events INTEGER, n_fit_rows INTEGER,
    worker TEXT, result TEXT,
    worker_pid INTEGER, worker_create_time REAL,
    retry_of TEXT, server_id TEXT, recovered INTEGER DEFAULT 0,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_key ON jobs(cache_key);
CREATE INDEX IF NOT EXISTS jobs_experiment ON jobs(experiment_id);
"""


class JobStore:
    """İş meta verisinin tek doğruluk kaynağı. İş parçacığı güvenli (tek bağlantı + kilit)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), timeout=15, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")  # durum değişikliği güç kesintisinde de kalıcı olsun
            self._db.executescript(_DDL)
            v = self._db.execute("PRAGMA user_version").fetchone()[0]
            if v == 0:
                self._db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            elif v != SCHEMA_VERSION:
                raise RuntimeError(f"İş kaydı şema sürümü {v}; beklenen {SCHEMA_VERSION}.")

    # ------------------------------------------------------------------ yardımcılar
    @staticmethod
    def _encode(fields: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for k, v in fields.items():
            if k not in COLUMNS:
                raise KeyError(f"Bilinmeyen iş alanı: {k}")
            out[k] = json.dumps(v, ensure_ascii=False, default=float) if k in JSON_COLS and v is not None else v
        return out

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for k in JSON_COLS:
            if d.get(k) is not None:
                d[k] = json.loads(d[k])
        d["recovered"] = bool(d.get("recovered"))
        return d

    # ------------------------------------------------------------------ yazma
    def insert(self, rec: dict[str, Any]) -> None:
        if rec["state"] not in STATES:
            raise ValueError(rec["state"])
        enc = self._encode({**rec, "updated_at": time.time()})
        cols = ", ".join(enc)
        with self._lock:
            self._db.execute(f"INSERT INTO jobs ({cols}) VALUES ({', '.join('?' * len(enc))})", tuple(enc.values()))

    def update(self, job_id: str, fields: dict[str, Any], expect: Iterable[str] | None = None) -> bool:
        """Alanları atomik olarak günceller. ``expect`` verilirse yalnızca mevcut durum bunlardan biriyse yazar
        (karşılaştır-ve-değiştir); yazılmadıysa False döner."""
        if "state" in fields and fields["state"] not in STATES:
            raise ValueError(fields["state"])
        enc = self._encode({**fields, "updated_at": time.time()})
        sql = f"UPDATE jobs SET {', '.join(f'{k} = ?' for k in enc)} WHERE job_id = ?"
        args: list[Any] = [*enc.values(), job_id]
        if expect is not None:
            exp = tuple(expect)
            sql += f" AND state IN ({', '.join('?' * len(exp))})"
            args += exp
        with self._lock:
            return self._db.execute(sql, args).rowcount == 1

    # ------------------------------------------------------------------ okuma
    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._decode(self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone())

    def list(self, limit: int = 200, states: Iterable[str] | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM jobs", []
        if states is not None:
            st = tuple(states)
            sql += f" WHERE state IN ({', '.join('?' * len(st))})"
            args += st
        sql += " ORDER BY submitted_at DESC, rowid DESC LIMIT ?"
        with self._lock:
            return [self._decode(r) for r in self._db.execute(sql, [*args, limit]).fetchall()]  # type: ignore[misc]

    def active_with_key(self, cache_key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._decode(self._db.execute(
                "SELECT * FROM jobs WHERE cache_key = ? AND state IN ('queued', 'running') ORDER BY submitted_at LIMIT 1",
                (cache_key,)).fetchone())

    def latest_completed(self, experiment_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._decode(self._db.execute(
                "SELECT * FROM jobs WHERE experiment_id = ? AND state = 'completed' ORDER BY finished_at DESC LIMIT 1",
                (experiment_id,)).fetchone())

    def count(self, states: Iterable[str]) -> int:
        st = tuple(states)
        with self._lock:
            return int(self._db.execute(f"SELECT COUNT(*) FROM jobs WHERE state IN ({', '.join('?' * len(st))})",
                                        st).fetchone()[0])

    def integrity(self) -> str:
        with self._lock:
            return str(self._db.execute("PRAGMA integrity_check").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._db.close()
