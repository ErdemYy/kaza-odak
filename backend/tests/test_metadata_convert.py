import json
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest
import requests

from conftest import FakeSession
from saferoute.data.convert import SIDECAR_NAME, snapshot_to_parquet
from saferoute.data.download import DownloadError, download_snapshot
from saferoute.data.loader import load_parquet, load_raw
from saferoute.data.metadata import acquisition_record, assess_freshness, check_source, write_record

QUIET = {"log": lambda _: None, "sleep": lambda _: None}
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def test_full_acquisition_record(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=FakeSession(rows), **QUIET)
    rec = acquisition_record(snap)
    assert rec["acquisition_status"] == "full"
    assert rec["row_count"] == rec["server_row_count"] == 7
    assert rec["column_count"] == 29
    assert rec["earliest_crash_date"].startswith("2020-01-01")
    assert len(rec["combined_sha256"]) == 64
    path = write_record(rec, "acq.json", tmp_path / "meta")
    assert json.loads(path.read_text(encoding="utf-8"))["snapshot"] == "s"


def test_partial_acquisition_is_never_reported_as_full(tmp_path, rows):
    snap = tmp_path / "s"
    with pytest.raises(DownloadError):
        download_snapshot(snapshot_dir=snap, page_size=3, max_retries=2,
                          session=FakeSession(rows, failures=[None, 503, 503]), **QUIET)
    rec = acquisition_record(snap)
    assert rec["acquisition_status"] == "partial"
    assert rec["row_count"] == 3 and rec["server_row_count"] == 7
    assert "temsil etmez" in rec["note"]


def test_record_requires_snapshot_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        acquisition_record(tmp_path)


@pytest.mark.parametrize("updated,freq,verdict", [
    ("2026-10-18T00:00:00+00:00", "Daily", "updating"),
    ("2026-06-15T23:05:47+00:00", "Daily", "stale"),
    ("2026-06-15T23:05:47+00:00", None, "unknown"),
    (None, "Daily", "unknown"),
])
def test_assess_freshness(updated, freq, verdict):
    assert assess_freshness(updated, freq, NOW)["verdict"] == verdict


def test_check_source_reports_unreachable_without_raising():
    class Down:
        headers: dict = {}

        def get(self, *a, **k):
            raise requests.ConnectionError("ağ yok")

    rec = check_source(Down(), NOW)
    assert rec["reachable"] is False and "ağ yok" in rec["error"]


def test_parquet_copy_is_lossless_and_idempotent(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "raw" / "s", page_size=3, session=FakeSession(rows), **QUIET)
    target = snapshot_to_parquet(snap, out_root=tmp_path / "interim")
    meta = json.loads((target.parent / SIDECAR_NAME).read_text(encoding="utf-8"))
    assert meta["row_count"] == 7 and meta["column_count"] == 29
    assert load_parquet(target).equals(load_raw(snap))
    mtime = target.stat().st_mtime_ns
    assert snapshot_to_parquet(snap, out_root=tmp_path / "interim") == target
    assert target.stat().st_mtime_ns == mtime          # aynı kaynaktan yeniden yazılmaz
    assert pq.read_schema(target).field("latitude").type == "string"
